from datetime import datetime, timedelta, timezone

from tests.test_points import buy, mk_customer, mk_reward


def ago(d):
    return (datetime.now(timezone.utc) - timedelta(days=d)).isoformat()


def seed_population(client, auth):
    ids = {}
    # high-value: many recent large purchases
    for i in range(3):
        cid = mk_customer(client, auth, email=f"hv{i}@x.io")
        for j in range(8):
            buy(client, auth, cid, 5000, f"hv{i}-{j}", occurred_at=ago(2 + j * 5))
        ids.setdefault("hv", []).append(cid)
    # at-risk: many purchases long-ish ago
    for i in range(3):
        cid = mk_customer(client, auth, email=f"ar{i}@x.io")
        for j in range(6):
            buy(client, auth, cid, 1500, f"ar{i}-{j}", occurred_at=ago(120 + j * 10))
        ids.setdefault("ar", []).append(cid)
    # inactive: one old purchase
    for i in range(2):
        cid = mk_customer(client, auth, email=f"in{i}@x.io")
        buy(client, auth, cid, 300, f"in{i}", occurred_at=ago(300))
        ids.setdefault("in", []).append(cid)
    # new: just joined
    ids["new"] = [mk_customer(client, auth, email="new@x.io")]
    return ids


def test_segmentation_rfm_and_kmeans(client, auth):
    ids = seed_population(client, auth)
    out = client.post("/api/segments/run", headers=auth).json()
    assert out["customers"] == 9 and len(out["clusters"]) == 4
    seg = lambda cid: client.get(f"/api/customers/{cid}/segment", headers=auth).json()["segment"]
    assert {seg(c) for c in ids["hv"]} == {"high_value"}
    assert {seg(c) for c in ids["ar"]} == {"at_risk"}
    assert {seg(c) for c in ids["in"]} == {"inactive"}
    assert seg(ids["new"][0]) == "new"
    summary = {s["segment"]: s for s in client.get("/api/segments", headers=auth).json()["summary"]}
    assert summary["high_value"]["customers"] == 3 and summary["high_value"]["rule"]


def test_reward_recommendation_ranking(client, auth):
    cid = mk_customer(client, auth, preferred_categories=["coffee"])
    for j in range(5):
        buy(client, auth, cid, 2000, f"c{j}", category="coffee")
    buy(client, auth, cid, 500, "b1", category="bakery")
    coffee = mk_reward(client, auth, cost=300, category="coffee")
    mk_reward(client, auth, cost=300, category="bakery")
    mk_reward(client, auth, cost=300, category="merch")
    mk_reward(client, auth, cost=50, tier="gold", category="coffee")  # ineligible tier → never recommended
    client.post("/api/segments/run", headers=auth)
    recs = client.get(f"/api/customers/{cid}/recommendations", headers=auth).json()
    assert recs[0]["reward_id"] == coffee and any("spend" in r for r in recs[0]["reasons"])
    assert all(r["points_cost"] != 50 for r in recs)
    assert [r["score"] for r in recs] == sorted([r["score"] for r in recs], reverse=True)
    # repetition penalty
    client.post(f"/api/customers/{cid}/redeem", headers=auth, json={"reward_id": coffee, "idempotency_key": "rep-0001"})
    recs2 = client.get(f"/api/customers/{cid}/recommendations", headers=auth).json()
    assert recs2[0]["reward_id"] != coffee


def test_campaign_generation_validation_and_approval_flow(client, auth, monkeypatch):
    from app.core import llm
    ids = seed_population(client, auth)
    client.post("/api/segments/run", headers=auth)
    rid = mk_reward(client, auth, cost=100)
    # LLM unavailable → honest 503
    r = client.post("/api/campaigns/generate", headers=auth, json={"objective": "Win back customers", "segment": "at_risk"})
    assert r.status_code == 503
    monkeypatch.setattr(llm, "llm_configured", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda m: {"name": "We miss you", "ideas": ["a", "b", "c"], "reward_id": 9999,
                        "message_template": "Hi {first_name}, you have {points_balance} pts. {hack}", "bonus_points": 99999})
    d = client.post("/api/campaigns/generate", headers=auth, json={"objective": "Win back customers", "segment": "at_risk"}).json()
    assert d["reward_id"] is None and d["validation"]["reward_id_rejected"]      # hallucinated reward dropped
    assert d["bonus_points"] == 1000 and "{hack}" not in d["message_template"]  # clamped + sanitized
    body = {k: d[k] for k in ("name", "objective", "segment", "message_template", "ideas")} | {"reward_id": rid, "bonus_points": 25, "generated_by": "llm"}
    c = client.post("/api/campaigns", headers=auth, json=body).json()
    assert c["status"] == "draft"
    assert client.post(f"/api/campaigns/{c['id']}/activate", headers=auth).status_code == 409  # must approve first
    assert client.post(f"/api/campaigns/{c['id']}/approve", headers=auth).json()["status"] == "approved"
    a = client.post(f"/api/campaigns/{c['id']}/activate", headers=auth).json()
    assert a["status"] == "active"
    rec = client.get(f"/api/campaigns/{c['id']}/recipients", headers=auth).json()
    assert len(rec) == 3 and "Hi Ravi" in rec[0]["message"]
    bal = client.get(f"/api/customers/{ids['ar'][0]}", headers=auth).json()["account"]["balance"]
    assert bal == 6 * 150 + 25  # bonus granted exactly once
    client.post(f"/api/customers/{ids['ar'][0]}/redeem", headers=auth, json={"reward_id": rid, "idempotency_key": "camp-red-1", "campaign_id": c["id"]})
    client.post(f"/api/campaigns/{c['id']}/events", headers=auth, json={"customer_id": ids["ar"][0], "kind": "opened"})
    assert client.post(f"/api/campaigns/{c['id']}/events", headers=auth, json={"customer_id": ids["hv"][0], "kind": "opened"}).status_code == 422
    m = client.get(f"/api/campaigns/{c['id']}/metrics", headers=auth).json()
    assert m["reach"] == 3 and m["opened"] == 1 and m["redeemers"] == 1 and m["redemption_rate"] == round(1 / 3, 4)
    dash = client.get("/api/analytics/dashboard", headers=auth).json()
    assert dash["points_redeemed"] == 100 and dash["campaigns"][0]["reach"] == 3
    actions = {a["action"] for a in client.get("/api/audit", headers=auth).json()}
    assert {"campaign.approved", "campaign.activated", "reward.redeemed", "purchase.recorded"} <= actions
