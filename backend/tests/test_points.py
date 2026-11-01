from datetime import datetime, timedelta, timezone


def mk_customer(client, auth, email="ravi@x.in", **kw):
    r = client.post("/api/customers", headers=auth, json={"first_name": "Ravi", "email": email, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def mk_reward(client, auth, cost=100, stock=5, tier="bronze", **kw):
    return client.post("/api/rewards", headers=auth, json={"name": f"R{cost}", "points_cost": cost, "stock": stock,
                                                           "min_tier": tier, **kw}).json()["id"]


def buy(client, auth, cid, amount, ref, **kw):
    return client.post(f"/api/customers/{cid}/purchases", headers=auth, json={"amount": amount, "external_ref": ref, **kw})


def test_customer_creation_and_welcome_bonus(client, auth):
    org = client.get("/api/org", headers=auth).json()
    client.put("/api/org", headers=auth, json={**org, "welcome_bonus": 50})
    cid = mk_customer(client, auth)
    c = client.get(f"/api/customers/{cid}", headers=auth).json()
    assert c["account"]["balance"] == 50 and c["account"]["tier"] == "bronze"
    assert client.post("/api/customers", headers=auth, json={"first_name": "Dup", "email": "ravi@x.in"}).status_code == 409


def test_points_calculation_and_tiers(client, auth):
    cid = mk_customer(client, auth)
    r = buy(client, auth, cid, 1234.5, "ORD-1").json()
    assert r["points_awarded"] == 123 and r["balance"] == 123          # default 0.1 pt per ₹ (floor)
    org = client.get("/api/org", headers=auth).json()
    client.put("/api/org", headers=auth, json={**org, "min_purchase_for_points": 500, "tier_silver_points": 200})
    assert buy(client, auth, cid, 499, "ORD-2").json()["points_awarded"] == 0
    r = buy(client, auth, cid, 1000, "ORD-3").json()
    assert r["balance"] == 223 and r["tier"] == "silver"


def test_duplicate_transaction_prevention(client, auth):
    cid = mk_customer(client, auth)
    assert buy(client, auth, cid, 1000, "POS-77").status_code == 201
    dup = buy(client, auth, cid, 1000, "POS-77")
    assert dup.status_code == 409 and "Duplicate" in dup.json()["detail"]
    assert client.get(f"/api/customers/{cid}", headers=auth).json()["account"]["balance"] == 100
    assert len(client.get(f"/api/customers/{cid}/ledger", headers=auth).json()) == 1


def test_reward_eligibility(client, auth):
    cid = mk_customer(client, auth)
    buy(client, auth, cid, 1000, "A")  # 100 pts, bronze
    gold = mk_reward(client, auth, cost=50, tier="gold")
    pricey = mk_reward(client, auth, cost=500)
    empty = mk_reward(client, auth, cost=10, stock=0)
    inactive = mk_reward(client, auth, cost=20, active=False)
    for rid, msg in [(gold, "gold tier"), (pricey, "more points"), (empty, "Out of stock"), (inactive, "inactive")]:
        r = client.post(f"/api/customers/{cid}/redeem", headers=auth, json={"reward_id": rid, "idempotency_key": f"key-{rid}-elig"})
        assert r.status_code == 422 and msg in r.json()["detail"], r.json()


def test_redemption_fifo_idempotency_and_stock(client, auth):
    cid = mk_customer(client, auth)
    buy(client, auth, cid, 600, "E1")
    buy(client, auth, cid, 600, "E2")   # 2 lots of 60
    rid = mk_reward(client, auth, cost=100, stock=1)
    r1 = client.post(f"/api/customers/{cid}/redeem", headers=auth, json={"reward_id": rid, "idempotency_key": "redeem-001"})
    assert r1.status_code == 201 and r1.json()["balance"] == 20
    again = client.post(f"/api/customers/{cid}/redeem", headers=auth, json={"reward_id": rid, "idempotency_key": "redeem-001"})
    assert again.json()["redemption_id"] == r1.json()["redemption_id"] and again.json()["balance"] == 20
    lots = sorted([e for e in client.get(f"/api/customers/{cid}/ledger", headers=auth).json() if e["kind"] == "earn"], key=lambda e: e["id"])
    assert [l["remaining"] for l in lots] == [0, 20]  # oldest consumed first
    assert next(r for r in client.get("/api/rewards", headers=auth).json() if r["id"] == rid)["stock"] == 0


def test_points_expiry(client, auth):
    cid = mk_customer(client, auth)
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    buy(client, auth, cid, 1000, "OLD", occurred_at=old)
    buy(client, auth, cid, 500, "NEW")
    assert client.post("/api/points/expire", headers=auth).json()["expired_points"] == 100
    assert client.get(f"/api/customers/{cid}", headers=auth).json()["account"]["balance"] == 50
    assert client.post("/api/points/expire", headers=auth).json()["expired_points"] == 0
