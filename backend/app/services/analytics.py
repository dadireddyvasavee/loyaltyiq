from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (Campaign, CampaignEvent, CampaignRecipient, Customer, CustomerSegment, LoyaltyAccount,
                        PointsLedger, Reward, RewardRedemption, Transaction)
from app.services.points import aware, now


def campaign_metrics(db: Session, c: Campaign) -> dict:
    recips = db.scalars(select(CampaignRecipient.customer_id).where(CampaignRecipient.campaign_id == c.id)).all()
    reach = len(recips)
    ev = dict(db.execute(select(CampaignEvent.kind, func.count(func.distinct(CampaignEvent.customer_id)))
                         .where(CampaignEvent.campaign_id == c.id).group_by(CampaignEvent.kind)).all())
    since = c.activated_at
    redeemed = purchased = 0
    if since and recips:
        redeemed = db.scalar(select(func.count(func.distinct(RewardRedemption.customer_id))).where(
            RewardRedemption.customer_id.in_(recips), RewardRedemption.occurred_at >= since)) or 0
        purchased = db.scalar(select(func.count(func.distinct(Transaction.customer_id))).where(
            Transaction.customer_id.in_(recips), Transaction.occurred_at >= since)) or 0
    rate = (lambda n: round(n / reach, 4) if reach else None)
    return {"campaign_id": c.id, "name": c.name, "segment": c.segment, "status": c.status, "reach": reach,
            "opened": ev.get("opened", 0), "clicked": ev.get("clicked", 0), "open_rate": rate(ev.get("opened", 0)),
            "click_rate": rate(ev.get("clicked", 0)), "redeemers": redeemed, "redemption_rate": rate(redeemed),
            "purchasers_after": purchased, "retention_rate": rate(purchased),
            "definitions": {"reach": "recipients at activation",
                            "redemption_rate": "recipients with ≥1 redemption after activation / reach",
                            "retention_rate": "recipients with ≥1 purchase after activation / reach",
                            "open/click": "recorded via POST /api/campaigns/{id}/events (e.g. ESP webhook)"}}


def dashboard(db: Session, org_id: int) -> dict:
    t = now()
    total = db.scalar(select(func.count()).select_from(Customer).where(Customer.organization_id == org_id))
    active = db.scalar(select(func.count(func.distinct(Transaction.customer_id))).where(
        Transaction.organization_id == org_id, Transaction.occurred_at >= t - timedelta(days=90)))
    led = dict(db.execute(select(PointsLedger.kind, func.sum(PointsLedger.points)).where(
        PointsLedger.organization_id == org_id).group_by(PointsLedger.kind)).all())
    issued = int((led.get("earn") or 0) + (led.get("bonus") or 0))
    redeemed = -int(led.get("redeem") or 0)
    expired = -int(led.get("expire") or 0)
    outstanding = db.scalar(select(func.sum(LoyaltyAccount.balance)).where(LoyaltyAccount.organization_id == org_id)) or 0
    seg = dict(db.execute(select(CustomerSegment.segment, func.count()).where(
        CustomerSegment.organization_id == org_id).group_by(CustomerSegment.segment)).all())
    tiers = dict(db.execute(select(LoyaltyAccount.tier, func.count()).where(
        LoyaltyAccount.organization_id == org_id).group_by(LoyaltyAccount.tier)).all())
    top = db.execute(select(Reward.name, func.count(RewardRedemption.id), func.sum(RewardRedemption.points_spent))
                     .join(RewardRedemption).where(Reward.organization_id == org_id).group_by(Reward.id)
                     .order_by(func.count(RewardRedemption.id).desc()).limit(5)).all()
    tx = db.execute(select(Transaction.occurred_at, Transaction.customer_id, Transaction.amount).where(
        Transaction.organization_id == org_id, Transaction.occurred_at >= t - timedelta(days=365))).all()
    months: dict[str, dict] = {}
    for at, cid, amt in tx:
        k = aware(at).strftime("%Y-%m")
        m = months.setdefault(k, {"month": k, "transactions": 0, "revenue": 0.0, "customers": set()})
        m["transactions"] += 1
        m["revenue"] += amt
        m["customers"].add(cid)
    trend = [{"month": k, "transactions": v["transactions"], "revenue": round(v["revenue"], 2),
              "active_customers": len(v["customers"])} for k, v in sorted(months.items())]
    camps = [campaign_metrics(db, c) for c in db.scalars(select(Campaign).where(
        Campaign.organization_id == org_id, Campaign.status.in_(["active", "completed"]))).all()]
    return {"total_customers": total, "active_members_90d": active, "points_issued": issued,
            "points_redeemed": redeemed, "points_expired": expired, "points_outstanding": int(outstanding),
            "points_utilization": round(redeemed / issued, 4) if issued else None,
            "segment_distribution": seg, "tier_distribution": tiers,
            "top_rewards": [{"name": n, "redemptions": c, "points": int(p or 0)} for n, c, p in top],
            "engagement_trend": trend, "campaigns": camps}
