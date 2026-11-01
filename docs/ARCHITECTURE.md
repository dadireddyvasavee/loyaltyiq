# LoyaltyIQ – Architecture

```mermaid
flowchart LR
  UI[React SPA – 12 pages<br/>role-aware UI] -- JWT / REST --> API[FastAPI<br/>RBAC + org scoping]
  subgraph Deterministic core
    RULES[Loyalty rules engine<br/>earn · tiers · expiry]
    PTS[Points ledger<br/>FIFO lots · idempotency · row locks]
    SEG[Segmentation service<br/>pandas RFM + scikit-learn K-means]
    REC[Reward recommendation service<br/>content + rule based]
    BEH[Behaviour analytics service]
    CMP[Campaign execution<br/>approve → activate → recipients]
  end
  subgraph AI layer – suggestions only
    GEN[LLM campaign generation<br/>ideas · copy · reward suggestion]
    PERS[Personalization<br/>safe placeholder rendering]
  end
  API --> RULES & PTS & SEG & REC & BEH & CMP
  API --> GEN
  GEN -- validated draft --> CMP
  CMP --> PERS
  GEN -. OpenAI-compatible .-> LLM[(LLM)]
  RULES & PTS & SEG & REC & BEH & CMP --> PG[(PostgreSQL)]
  API --> AUD[(audit_logs)]
```

## Separation of business rules and AI
The LLM only **proposes** campaign name, ideas, message copy, a reward id and bonus points. The backend then:
* drops any reward id that isn't an active, in-stock reward of **this** organization;
* clamps bonus points to 0–1000;
* strips unknown `{placeholders}`;
* stores the result as a **draft**. A human must approve it before it can be activated.
Points, eligibility, redemptions, recipients and metrics are 100 % deterministic code.

## Points ledger
| Concern | Mechanism |
|---|---|
| Duplicate purchase | `UNIQUE(organization_id, external_ref)` on transactions + pre-check → HTTP 409 |
| Duplicate redemption | `UNIQUE(organization_id, idempotency_key)`; retries return the original redemption |
| Concurrent redemption | `SELECT … FOR UPDATE` on account + reward + lots; conditional `UPDATE … WHERE stock > 0` |
| Negative balance/stock | DB `CHECK` constraints |
| Expiry | Each earn is a lot with `remaining` + `expires_at`; spending is FIFO; expiry job zeroes expired lots and writes `expire` entries |

## Multi-tenancy & RBAC
Every table has `organization_id`. Every query is scoped to the caller's org; cross-org IDs return 404 (no existence leak).
Roles: **owner** (all + user management), **admin** (all write operations), **analyst** (read-only).

## Tables
organizations · users · customers · loyalty_accounts · transactions · points_ledger · rewards · reward_redemptions · customer_segments · campaigns · campaign_recipients · campaign_events · audit_logs
