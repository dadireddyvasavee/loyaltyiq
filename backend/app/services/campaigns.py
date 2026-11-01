"""Campaign builder. LLM drafts content; deterministic code validates and executes.

Lifecycle: draft → approved (owner/admin, not by the creator of an LLM draft unless they're the only owner)
→ active (recipients resolved from the CURRENT segment, messages personalised, optional bonus points granted
idempotently) → completed.
"""
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import llm
from app.models import Campaign, CampaignEvent, CampaignRecipient, Customer, CustomerSegment, Organization, Reward
from app.services import audit, points, segmentation

PLACEHOLDERS = {"first_name", "points_balance", "tier", "reward_name", "business_name"}
MAX_BONUS = 1000


def render(template: str, customer: Customer, reward: Reward | None, org: Organization) -> str:
    vals = {"first_name": customer.first_name, "points_balance": str(customer.account.balance if customer.account else 0),
            "tier": customer.account.tier if customer.account else "bronze",
            "reward_name": reward.name if reward else "", "business_name": org.name}
    return re.sub(r"\{(\w+)\}", lambda m: vals.get(m.group(1), m.group(0)), template)


def validate_template(t: str) -> None:
    bad = set(re.findall(r"\{(\w+)\}", t)) - PLACEHOLDERS
    if bad:
        raise HTTPException(422, f"Unknown placeholders {sorted(bad)}; allowed: {sorted(PLACEHOLDERS)}")


def generate(db: Session, org: Organization, objective: str, segment: str, tone: str) -> dict:
    if segment not in segmentation.SEGMENTS:
        raise HTTPException(422, f"Unknown segment; choose from {segmentation.SEGMENTS}")
    stats = next((s for s in segmentation.summary(db, org.id) if s["segment"] == segment), None)
    rewards = db.scalars(select(Reward).where(Reward.organization_id == org.id, Reward.active.is_(True),
                                              Reward.stock > 0)).all()
    catalog = [{"id": r.id, "name": r.name, "category": r.category, "points_cost": r.points_cost,
                "min_tier": r.min_tier} for r in rewards]
    try:
        out = llm.chat_json([
            {"role": "system", "content": (
                "You are a loyalty marketing strategist. Return ONLY JSON with keys: name (string), "
                "ideas (array of 3 short campaign ideas), message_template (<= 400 chars, may use placeholders "
                f"{sorted('{'+p+'}' for p in PLACEHOLDERS)}), reward_id (one id from the provided rewards or null), "
                f"bonus_points (integer 0-{MAX_BONUS}), rationale (string). Do not invent rewards, discounts or prices.")},
            {"role": "user", "content": f"Business: {org.name}\nObjective: {objective}\nTarget segment: {segment} "
                                        f"({dict(segmentation.SEGMENT_RULES)[segment]})\nSegment stats: {stats}\n"
                                        f"Tone: {tone}\nAvailable rewards: {catalog}"}])
    except llm.LLMUnavailable as e:
        raise HTTPException(503, f"AI campaign generation unavailable: {e}. You can still create the campaign manually.")
    valid_ids = {r["id"] for r in catalog}
    rid = out.get("reward_id") if out.get("reward_id") in valid_ids else None
    tmpl = str(out.get("message_template", ""))[:600]
    tmpl = re.sub(r"\{(\w+)\}", lambda m: m.group(0) if m.group(1) in PLACEHOLDERS else m.group(1), tmpl)
    bonus = out.get("bonus_points", 0)
    return {"name": str(out.get("name", "AI campaign"))[:200], "objective": objective, "segment": segment,
            "ideas": [str(i) for i in out.get("ideas", [])][:5], "message_template": tmpl, "reward_id": rid,
            "bonus_points": max(0, min(MAX_BONUS, int(bonus))) if isinstance(bonus, (int, float)) else 0,
            "rationale": str(out.get("rationale", "")), "validation": {
                "reward_id_rejected": out.get("reward_id") is not None and rid is None}}


def approve(db: Session, org: Organization, c: Campaign, user) -> Campaign:
    if c.status != "draft":
        raise HTTPException(409, f"Only drafts can be approved (status={c.status})")
    validate_template(c.message_template)
    c.status, c.approved_by = "approved", user.id
    audit.log(db, org.id, user.id, "campaign.approved", "campaign", c.id)
    db.commit()
    return c


def activate(db: Session, org: Organization, c: Campaign, user) -> Campaign:
    if c.status != "approved":
        raise HTTPException(409, "Campaign must be reviewed and approved before activation")
    if c.reward_id:
        r = db.get(Reward, c.reward_id)
        if not r or r.organization_id != org.id or not r.active:
            raise HTTPException(422, "Campaign reward is no longer available")
    ids = db.scalars(select(CustomerSegment.customer_id).where(CustomerSegment.organization_id == org.id,
                                                               CustomerSegment.segment == c.segment)).all()
    if not ids:
        raise HTTPException(422, "Target segment is empty — run segmentation first")
    for cust in db.scalars(select(Customer).where(Customer.id.in_(ids))).unique():
        db.add(CampaignRecipient(campaign_id=c.id, customer_id=cust.id, message=render(c.message_template, cust, c.reward, org)))
        db.add(CampaignEvent(campaign_id=c.id, customer_id=cust.id, kind="sent"))
        if c.bonus_points:
            points.grant_bonus(db, org, cust.id, c.bonus_points, f"campaign:{c.id}", f"Campaign bonus: {c.name}", user.id)
    c.status, c.activated_at = "active", points.now()
    audit.log(db, org.id, user.id, "campaign.activated", "campaign", c.id, recipients=len(ids))
    db.commit()
    return c
