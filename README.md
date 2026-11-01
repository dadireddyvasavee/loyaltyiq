# LoyaltyIQ — AI-Driven Customer Loyalty, Rewards & Personalization Platform

A multi-tenant loyalty SaaS MVP. Businesses run a points program, segment customers (RFM + K-means), get **per-customer reward recommendations with reasons**, and build **AI-drafted campaigns that a human must approve** before they go out. Everything is measured on an analytics dashboard.

**Stack:** React 18 · TypeScript · Vite · Tailwind · Recharts | FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic | PostgreSQL | pandas · scikit-learn · OpenAI-compatible LLM | Docker · GitHub Actions · Pytest
Architecture, ledger guarantees and the AI/rules separation: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Feature map
| Module | Highlights |
|---|---|
| Customers | Registration, profiles, preferred categories, purchase history, ledger, redemptions, search + segment/tier filters |
| Points engine | Configurable earn rate, minimum purchase, tiers, welcome bonus, FIFO expiry, idempotent purchases (409 on duplicate), idempotent + locked redemptions |
| Rewards | Catalog with cost, stock, min tier, validity, active flag; eligibility checks with clear reasons |
| Segmentation | RFM percentile scores → rule-based segments (high_value, loyal, regular, new, at_risk, inactive) + K-means clusters; rules shown in the UI |
| Reward recommendations | Spend affinity, preferences, segment rules, affordability, redemption history, repetition penalty; explanations per reward |
| AI campaign builder | Objective → segment → LLM ideas + personalised message + reward suggestion → edit → save draft → **approve** → activate |
| Campaign analytics | Reach, open/click (recorded events), redemption rate, retention rate, segment performance, metric definitions |
| Dashboard | Customers, active members, points issued/redeemed/expired/outstanding, utilization, segment and tier distribution, top rewards, campaign performance, 12-month engagement trend |
| Security | JWT, PBKDF2 password hashing, RBAC (owner/admin/analyst), org-level isolation, audit log, secrets only in backend env |

## Quick start (Docker)
```bash
cp backend/.env.example backend/.env    # add LLM_API_KEY for AI campaign generation
docker compose up --build
```
App: http://localhost:8080 · Swagger: http://localhost:8000/docs
With `SEED_SYNTHETIC=true` (the default in compose), a **synthetic** demo org is created: **demo@loyaltyiq.demo / demo12345** (owner) and **analyst@loyaltyiq.demo / demo12345** (read-only). It contains 300 fictional customers, about 3,000 transactions, rewards and redemptions, all produced through the real points engine. The org is flagged and bannered as SYNTHETIC in the UI.

## Local development
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
alembic upgrade head
python -m app.cli seed-synthetic          # optional
uvicorn app.main:app --reload
cd ../frontend && npm install && npm run dev
```
Schedule `python -m app.cli expire` daily (cron or a container job) to expire points.

## Demo walkthrough
1. Sign in as the demo owner → **Dashboard**.
2. **Segmentation** → *Re-run segmentation* → inspect the rules table, scatter plot and K-means clusters.
3. **AI recommendations** → pick `at_risk` → see each customer's best reward and why.
4. **Customers** → open a profile → record a purchase (try the same reference twice to see the 409) → redeem a reward.
5. **Campaign builder** → objective "Win back lapsed regulars", segment `at_risk` → *Generate with AI* → edit → save → **Approve** → **Activate**.
6. **Campaign analytics** → reach and redemption rate update from real redemptions made after activation.
7. Sign in as the analyst → write actions are hidden in the UI and rejected with 403 by the API.

## Tests
```bash
cd backend && pytest -q    # 11 tests
```
Covers customer creation, point calculation and tiers, duplicate-transaction prevention, reward eligibility (tier, stock, inactive, balance), FIFO + idempotent redemption + stock, expiry, RFM segmentation + K-means, recommendation ranking + repetition penalty, campaign generation validation (hallucinated reward rejected, bonus clamped, placeholders sanitised), approve-before-activate, campaign metrics, audit log, org isolation and RBAC.

## Deployment
Backend container (runs `alembic upgrade head` on start) plus managed PostgreSQL, and the frontend as a static site or nginx container (included). This works on Render, Railway, Fly.io or Azure Container Apps. Set a strong `JWT_SECRET` and `SEED_SYNTHETIC=false` in production.

## Known limitations
- Open and click events must be posted by your messaging provider (`POST /api/campaigns/{id}/events`). No email or SMS sending is included, and no engagement is ever simulated.
- Without an LLM key, AI campaign generation returns HTTP 503 with a clear message. Manual campaigns work fully.
- Segmentation runs on demand (button or API), not on a schedule.
- Row locks (`FOR UPDATE`) take effect on PostgreSQL. The SQLite test database ignores them, so concurrency safety in tests relies on the unique constraints.
- No screenshots are bundled. Capture them from your running instance.
