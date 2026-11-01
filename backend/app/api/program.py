from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org, current_user, scoped, writer
from app.core.db import get_db
from app.models import (Campaign, CampaignEvent, CampaignRecipient, Customer, CustomerSegment, Organization, Reward,
                        User)
from app.schemas import CampaignGenIn, CampaignIn, CampaignOut, EventIn, RewardIn, RewardOut
from app.services import analytics, audit, campaigns, points, rewards_rec, segmentation

router = APIRouter(prefix="/api", tags=["rewards, segments, campaigns, analytics"])


# ---------- rewards ----------
@router.get("/rewards", response_model=list[RewardOut])
def rewards(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Reward).where(Reward.organization_id == user.organization_id).order_by(Reward.points_cost)).all()


@router.post("/rewards", response_model=RewardOut, status_code=201)
def create_reward(body: RewardIn, db: Session = Depends(get_db), user: User = Depends(writer)):
    r = Reward(organization_id=user.organization_id, **body.model_dump())
    db.add(r)
    db.flush()
    audit.log(db, user.organization_id, user.id, "reward.created", "reward", r.id, **body.model_dump(exclude={"valid_until"}))
    db.commit()
    return r


@router.put("/rewards/{rid}", response_model=RewardOut)
def update_reward(rid: int, body: RewardIn, db: Session = Depends(get_db), user: User = Depends(writer)):
    r = scoped(db, Reward, rid, user.organization_id, "Reward")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit.log(db, user.organization_id, user.id, "reward.updated", "reward", r.id)
    db.commit()
    return r


# ---------- points ----------
@router.post("/points/expire")
def expire(db: Session = Depends(get_db), org: Organization = Depends(current_org), user: User = Depends(writer)):
    return {"expired_points": points.expire_points(db, org)}


# ---------- segmentation ----------
@router.post("/segments/run")
def run_segmentation(k: int = 4, db: Session = Depends(get_db), user: User = Depends(writer)):
    out = segmentation.run(db, user.organization_id, k=max(2, min(k, 8)))
    audit.log(db, user.organization_id, user.id, "segmentation.run", "organization", user.organization_id,
              customers=out["customers"])
    db.commit()
    return out


@router.get("/segments")
def segments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(CustomerSegment).where(CustomerSegment.organization_id == user.organization_id)).all()
    clusters: dict[int, list] = {}
    for r in rows:
        if r.cluster is not None:
            clusters.setdefault(r.cluster, []).append(r)
    cl = [{"cluster": c, "size": len(v), "avg_recency_days": round(sum(min(x.recency_days, 3650) for x in v) / len(v), 1),
           "avg_frequency": round(sum(x.frequency for x in v) / len(v), 2),
           "avg_monetary": round(sum(x.monetary for x in v) / len(v), 2),
           "dominant_segment": max({x.segment for x in v}, key=lambda s: sum(1 for x in v if x.segment == s))}
          for c, v in sorted(clusters.items())]
    points_ = [{"customer_id": r.customer_id, "segment": r.segment, "recency_days": min(r.recency_days, 730),
                "frequency": r.frequency, "monetary": r.monetary} for r in rows[:1000]]
    return {"summary": segmentation.summary(db, user.organization_id), "rules": segmentation.SEGMENT_RULES,
            "clusters": cl, "scatter": points_, "last_run": max((r.created_at for r in rows), default=None)}


# ---------- reward recommendations (dashboard) ----------
@router.get("/recommendations")
def rec_overview(segment: str | None = None, limit: int = 25, db: Session = Depends(get_db),
                 org: Organization = Depends(current_org), user: User = Depends(current_user)):
    stmt = select(Customer).join(CustomerSegment, CustomerSegment.customer_id == Customer.id).where(
        Customer.organization_id == org.id)
    if segment:
        stmt = stmt.where(CustomerSegment.segment == segment)
    out = []
    for c in db.scalars(stmt.order_by(CustomerSegment.monetary.desc()).limit(min(limit, 100))).unique():
        recs = rewards_rec.recommend(db, org, c, limit=1)
        seg = db.scalar(select(CustomerSegment.segment).where(CustomerSegment.customer_id == c.id))
        out.append({"customer_id": c.id, "name": f"{c.first_name} {c.last_name}".strip(), "segment": seg,
                    "balance": c.account.balance, "tier": c.account.tier, "top_reward": recs[0] if recs else None})
    return out


# ---------- campaigns ----------
@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Campaign).where(Campaign.organization_id == user.organization_id)
                      .order_by(Campaign.id.desc())).unique().all()


@router.post("/campaigns/generate")
def generate(body: CampaignGenIn, db: Session = Depends(get_db), org: Organization = Depends(current_org),
             user: User = Depends(writer)):
    """LLM drafts a campaign (NOT saved). Review/edit it, then POST /campaigns to save as draft."""
    return campaigns.generate(db, org, body.objective, body.segment, body.tone)


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignIn, db: Session = Depends(get_db), user: User = Depends(writer)):
    if body.segment not in segmentation.SEGMENTS:
        raise HTTPException(422, f"Unknown segment; choose from {segmentation.SEGMENTS}")
    campaigns.validate_template(body.message_template)
    if body.reward_id:
        scoped(db, Reward, body.reward_id, user.organization_id, "Reward")
    c = Campaign(organization_id=user.organization_id, created_by=user.id, **body.model_dump())
    db.add(c)
    db.flush()
    audit.log(db, user.organization_id, user.id, "campaign.created", "campaign", c.id, generated_by=body.generated_by)
    db.commit()
    return c


@router.put("/campaigns/{cid}", response_model=CampaignOut)
def update_campaign(cid: int, body: CampaignIn, db: Session = Depends(get_db), user: User = Depends(writer)):
    c = scoped(db, Campaign, cid, user.organization_id, "Campaign")
    if c.status != "draft":
        raise HTTPException(409, "Only drafts can be edited")
    campaigns.validate_template(body.message_template)
    if body.reward_id:
        scoped(db, Reward, body.reward_id, user.organization_id, "Reward")
    for k, v in body.model_dump(exclude={"generated_by"}).items():
        setattr(c, k, v)
    audit.log(db, user.organization_id, user.id, "campaign.updated", "campaign", c.id)
    db.commit()
    return c


@router.get("/campaigns/{cid}/preview")
def preview(cid: int, db: Session = Depends(get_db), org: Organization = Depends(current_org),
            user: User = Depends(current_user)):
    c = scoped(db, Campaign, cid, org.id, "Campaign")
    ids = db.scalars(select(CustomerSegment.customer_id).where(CustomerSegment.organization_id == org.id,
                                                               CustomerSegment.segment == c.segment)).all()
    sample = db.scalars(select(Customer).where(Customer.id.in_(ids)).limit(3)).unique().all()
    return {"audience_size": len(ids), "samples": [{"customer": f"{s.first_name} {s.last_name}",
                                                    "message": campaigns.render(c.message_template, s, c.reward, org)}
                                                   for s in sample]}


@router.post("/campaigns/{cid}/approve", response_model=CampaignOut)
def approve(cid: int, db: Session = Depends(get_db), org: Organization = Depends(current_org), user: User = Depends(writer)):
    return campaigns.approve(db, org, scoped(db, Campaign, cid, org.id, "Campaign"), user)


@router.post("/campaigns/{cid}/activate", response_model=CampaignOut)
def activate(cid: int, db: Session = Depends(get_db), org: Organization = Depends(current_org), user: User = Depends(writer)):
    return campaigns.activate(db, org, scoped(db, Campaign, cid, org.id, "Campaign"), user)


@router.post("/campaigns/{cid}/complete", response_model=CampaignOut)
def complete(cid: int, db: Session = Depends(get_db), user: User = Depends(writer)):
    c = scoped(db, Campaign, cid, user.organization_id, "Campaign")
    if c.status != "active":
        raise HTTPException(409, "Only active campaigns can be completed")
    c.status = "completed"
    audit.log(db, user.organization_id, user.id, "campaign.completed", "campaign", c.id)
    db.commit()
    return c


@router.post("/campaigns/{cid}/events", status_code=201)
def record_event(cid: int, body: EventIn, db: Session = Depends(get_db), user: User = Depends(writer)):
    """Record engagement (e.g. from an email/SMS provider webhook). Only real recipients are accepted."""
    c = scoped(db, Campaign, cid, user.organization_id, "Campaign")
    if not db.scalar(select(CampaignRecipient.id).where(CampaignRecipient.campaign_id == c.id,
                                                        CampaignRecipient.customer_id == body.customer_id)):
        raise HTTPException(422, "Customer is not a recipient of this campaign")
    db.add(CampaignEvent(campaign_id=c.id, customer_id=body.customer_id, kind=body.kind))
    db.commit()
    return {"ok": True}


@router.get("/campaigns/{cid}/recipients")
def recipients(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    scoped(db, Campaign, cid, user.organization_id, "Campaign")
    rows = db.execute(select(CampaignRecipient, Customer).join(Customer).where(CampaignRecipient.campaign_id == cid)
                      .limit(500)).unique().all()
    return [{"customer_id": c.id, "name": f"{c.first_name} {c.last_name}", "message": r.message} for r, c in rows]


@router.get("/campaigns/{cid}/metrics")
def metrics(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return analytics.campaign_metrics(db, scoped(db, Campaign, cid, user.organization_id, "Campaign"))


# ---------- analytics ----------
@router.get("/analytics/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return analytics.dashboard(db, user.organization_id)


@router.get("/analytics/segments")
def segment_performance(db: Session = Depends(get_db), user: User = Depends(current_user)):
    out = []
    for s in segmentation.summary(db, user.organization_id):
        camps = db.scalars(select(Campaign).where(Campaign.organization_id == user.organization_id,
                                                  Campaign.segment == s["segment"],
                                                  Campaign.status.in_(["active", "completed"]))).all()
        ms = [analytics.campaign_metrics(db, c) for c in camps]
        reach = sum(m["reach"] for m in ms)
        out.append(s | {"campaigns": len(ms), "campaign_reach": reach,
                        "campaign_redemption_rate": round(sum(m["redeemers"] for m in ms) / reach, 4) if reach else None,
                        "campaign_retention_rate": round(sum(m["purchasers_after"] for m in ms) / reach, 4) if reach else None})
    return out
