"""Content-based + rule-based reward recommendations with explanations.

score = 0.35 category_affinity        share of the customer's spend in the reward's category
      + 0.20 preference_match         reward category ∈ customer's stated preferred categories
      + 0.20 segment_rule             segment-specific business rule (see SEGMENT_BOOST)
      + 0.15 affordability            1 if affordable now, partial if within 25 % of balance
      + 0.10 redemption_history       redeemed rewards in the same category before (content-based)
      − 0.60 if the same reward was redeemed in the last 30 days (avoid repetition)
Ineligible rewards (inactive, expired, out of stock, tier too low) are never recommended.
"""
from collections import Counter
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer, CustomerSegment, Organization, Reward, RewardRedemption, Transaction
from app.services.points import TIER_ORDER, aware, now

SEGMENT_BOOST = {
    "at_risk": (lambda r, bal: r.points_cost <= max(bal, 1) * 1.0, "Low-cost win-back reward for an at-risk customer"),
    "inactive": (lambda r, bal: r.points_cost <= 300, "Entry-level reward to re-activate an inactive customer"),
    "high_value": (lambda r, bal: r.category in ("experience", "vip") or r.points_cost >= 1000, "Premium reward suited to a high-value customer"),
    "new": (lambda r, bal: r.points_cost <= 200, "Quick first win for a new member"),
    "loyal": (lambda r, bal: True, "Loyal customer — any relevant reward"),
}


def recommend(db: Session, org: Organization, customer: Customer, limit: int = 5) -> list[dict]:
    acc = customer.account
    bal = acc.balance if acc else 0
    tier = acc.tier if acc else "bronze"
    spend = dict(db.execute(select(Transaction.category, func.sum(Transaction.amount)).where(
        Transaction.customer_id == customer.id).group_by(Transaction.category)).all())
    total = sum(spend.values()) or 1.0
    reds = db.scalars(select(RewardRedemption).where(RewardRedemption.customer_id == customer.id)).unique().all()
    red_cats = Counter(r.reward.category for r in reds)
    recent = {r.reward_id for r in reds if aware(r.occurred_at) >= now() - timedelta(days=30)}
    seg = db.scalar(select(CustomerSegment.segment).where(CustomerSegment.customer_id == customer.id))
    out = []
    for r in db.scalars(select(Reward).where(Reward.organization_id == org.id, Reward.active.is_(True), Reward.stock > 0)):
        if r.valid_until and aware(r.valid_until) < now():
            continue
        if TIER_ORDER.get(tier, 0) < TIER_ORDER.get(r.min_tier, 0):
            continue
        reasons, s = [], 0.0
        aff = spend.get(r.category, 0) / total
        if aff > 0:
            s += 0.35 * aff
            reasons.append(f"{aff:.0%} of their spend is in {r.category}")
        if r.category in (customer.preferred_categories or []):
            s += 0.20
            reasons.append(f"Matches stated preference: {r.category}")
        if seg in SEGMENT_BOOST and SEGMENT_BOOST[seg][0](r, bal):
            s += 0.20
            reasons.append(SEGMENT_BOOST[seg][1])
        if bal >= r.points_cost:
            s += 0.15
            reasons.append(f"Affordable now ({bal} pts ≥ {r.points_cost})")
        elif bal >= 0.75 * r.points_cost:
            s += 0.07
            reasons.append(f"Only {r.points_cost - bal} pts away")
        if red_cats.get(r.category):
            s += 0.10 * min(1, red_cats[r.category] / 2)
            reasons.append(f"Previously redeemed {red_cats[r.category]} {r.category} reward(s)")
        if r.id in recent:
            s -= 0.60
            reasons.append("Penalised: same reward redeemed in the last 30 days")
        out.append({"reward_id": r.id, "name": r.name, "category": r.category, "points_cost": r.points_cost,
                    "affordable": bal >= r.points_cost, "score": round(s, 4), "reasons": reasons or ["Eligible reward"]})
    out.sort(key=lambda x: (-x["score"], x["points_cost"]))
    return out[:limit]
