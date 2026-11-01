from tests.conftest import register
from tests.test_points import buy, mk_customer, mk_reward


def test_organization_isolation(client, auth):
    cid = mk_customer(client, auth)
    rid = mk_reward(client, auth)
    other = register(client, org="Rival Co", email="owner@rival.io")
    assert client.get(f"/api/customers/{cid}", headers=other).status_code == 404
    assert client.get("/api/customers", headers=other).json() == []
    assert buy(client, other, cid, 100, "X").status_code == 404
    assert client.put(f"/api/rewards/{rid}", headers=other, json={"name": "x", "points_cost": 1, "stock": 1}).status_code == 404
    # same external_ref in different orgs is allowed (idempotency is per-organization)
    oc = mk_customer(client, other, email="o@o.io")
    assert buy(client, auth, cid, 100, "SAME").status_code == 201 and buy(client, other, oc, 100, "SAME").status_code == 201


def test_role_based_access(client, auth):
    assert client.post("/api/org/users", headers=auth, json={"email": "an@acme.io", "full_name": "An", "password": "password1", "role": "analyst"}).status_code == 201
    tok = client.post("/api/auth/login", json={"email": "an@acme.io", "password": "password1"}).json()["access_token"]
    analyst = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/analytics/dashboard", headers=analyst).status_code == 200      # read ok
    assert client.post("/api/customers", headers=analyst, json={"first_name": "x", "email": "x@x.io"}).status_code == 403
    assert client.post("/api/segments/run", headers=analyst).status_code == 403
    assert client.post("/api/org/users", headers=analyst, json={"email": "z@acme.io", "full_name": "z", "password": "password1", "role": "admin"}).status_code == 403
    assert client.get("/api/audit", headers=analyst).status_code == 403
    assert client.get("/api/customers").status_code == 401
