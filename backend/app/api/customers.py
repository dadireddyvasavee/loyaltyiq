from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_org, current_user, scoped, writer
from app.core.db import get_db
from app.models import (Customer, CustomerSegment, LoyaltyAccount, Organization, PointsLedger, RewardRedemption,
                        Transaction, User)
from app.schemas import CustomerIn, CustomerOut, PurchaseIn, RedeemIn
from app.services import audit, points, rewards_rec

router = APIRouter(prefix="/api/customers", tags=["customers & points"])


def _out(c: Customer, seg: str | None) -> CustomerOut:
    return CustomerOut.model_validate(c).model_copy(update={"segment": seg})


@router.get("", response_model=list[CustomerOut])
def list_customers(q: str | None = None, segment: str | None = None, tier: str | None = None, limit: int = 200,
                   db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = (select(Customer, CustomerSegment.segment).outerjoin(CustomerSegment, CustomerSegment.customer_id == Customer.id)
            .join(LoyaltyAccount, LoyaltyAccount.customer_id == Customer.id)
            .where(Customer.organization_id == user.organization_id))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Customer.first_name.ilike(like), Customer.last_name.ilike(like), Customer.email.ilike(like)))
    if segment:
        stmt = stmt.where(CustomerSegment.segment == segment)
    if tier:
        stmt = stmt.where(LoyaltyAccount.tier == tier)
    rows = db.execute(stmt.order_by(LoyaltyAccount.lifetime_points.desc()).limit(min(limit, 1000))).unique().all()
    return [_out(c, s) for c, s in rows]


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerIn, db: Session = Depends(get_db), org: Organization = Depends(current_org),
                    user: User = Depends(writer)):
    if db.scalar(select(Customer.id).where(Customer.organization_id == org.id, Customer.email == body.email.lower())):
        raise HTTPException(409, "Customer with this email already exists")
    c = Customer(organization_id=org.id, **(body.model_dump() | {"email": body.email.lower()}))
    c.account = LoyaltyAccount(organization_id=org.id)
    db.add(c)
    db.flush()
    audit.log(db, org.id, user.id, "customer.created", "customer", c.id)
    if org.welcome_bonus:
        points.grant_bonus(db, org, c.id, org.welcome_bonus, f"welcome:{c.id}", "Welcome bonus", user.id)
    db.commit()
    db.refresh(c)
    return _out(c, None)


@router.get("/{cid}", response_model=CustomerOut)
def get_customer(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = scoped(db, Customer, cid, user.organization_id, "Customer")
    return _out(c, db.scalar(select(CustomerSegment.segment).where(CustomerSegment.customer_id == cid)))


@router.put("/{cid}", response_model=CustomerOut)
def update_customer(cid: int, body: CustomerIn, db: Session = Depends(get_db), user: User = Depends(writer)):
    c = scoped(db, Customer, cid, user.organization_id, "Customer")
    for k, v in body.model_dump().items():
        setattr(c, k, v.lower() if k == "email" else v)
    audit.log(db, user.organization_id, user.id, "customer.updated", "customer", c.id)
    db.commit()
    return _out(c, db.scalar(select(CustomerSegment.segment).where(CustomerSegment.customer_id == cid)))


@router.get("/{cid}/segment")
def segment(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    scoped(db, Customer, cid, user.organization_id, "Customer")
    s = db.scalar(select(CustomerSegment).where(CustomerSegment.customer_id == cid))
    if not s:
        return None
    return {k: getattr(s, k) for k in ("segment", "reason", "recency_days", "frequency", "monetary", "r_score",
                                       "f_score", "m_score", "redemptions", "engagement_events", "cluster")}


@router.get("/{cid}/transactions")
def transactions(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    scoped(db, Customer, cid, user.organization_id, "Customer")
    rows = db.scalars(select(Transaction).where(Transaction.customer_id == cid).order_by(Transaction.occurred_at.desc())).all()
    return [{"id": t.id, "external_ref": t.external_ref, "amount": t.amount, "category": t.category,
             "occurred_at": t.occurred_at, "points_awarded": t.points_awarded} for t in rows]


@router.get("/{cid}/ledger")
def ledger(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = scoped(db, Customer, cid, user.organization_id, "Customer")
    rows = db.scalars(select(PointsLedger).where(PointsLedger.account_id == c.account.id)
                      .order_by(PointsLedger.occurred_at.desc(), PointsLedger.id.desc())).all()
    return [{"id": e.id, "kind": e.kind, "points": e.points, "remaining": e.remaining, "expires_at": e.expires_at,
             "note": e.note, "occurred_at": e.occurred_at} for e in rows]


@router.get("/{cid}/redemptions")
def redemptions(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    scoped(db, Customer, cid, user.organization_id, "Customer")
    rows = db.scalars(select(RewardRedemption).where(RewardRedemption.customer_id == cid)
                      .order_by(RewardRedemption.occurred_at.desc())).unique().all()
    return [{"id": r.id, "reward": r.reward.name, "points_spent": r.points_spent, "occurred_at": r.occurred_at,
             "campaign_id": r.campaign_id} for r in rows]


@router.post("/{cid}/purchases", status_code=201)
def purchase(cid: int, body: PurchaseIn, db: Session = Depends(get_db), org: Organization = Depends(current_org),
             user: User = Depends(writer)):
    c = scoped(db, Customer, cid, org.id, "Customer")
    t = points.record_purchase(db, org, c, body.amount, body.external_ref, body.category, body.occurred_at, user.id)
    db.refresh(c.account)
    return {"transaction_id": t.id, "points_awarded": t.points_awarded, "balance": c.account.balance, "tier": c.account.tier}


@router.post("/{cid}/redeem", status_code=201)
def redeem(cid: int, body: RedeemIn, db: Session = Depends(get_db), org: Organization = Depends(current_org),
           user: User = Depends(writer)):
    scoped(db, Customer, cid, org.id, "Customer")
    r = points.redeem(db, org, cid, body.reward_id, body.idempotency_key, user.id, body.campaign_id)
    acc = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.customer_id == cid))
    return {"redemption_id": r.id, "points_spent": r.points_spent, "balance": acc.balance}


@router.get("/{cid}/recommendations")
def recommendations(cid: int, db: Session = Depends(get_db), org: Organization = Depends(current_org),
                    user: User = Depends(current_user)):
    return rewards_rec.recommend(db, org, scoped(db, Customer, cid, org.id, "Customer"))
