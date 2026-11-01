"""Loyalty points engine — deterministic, transactional, idempotent.

* Earning: one ledger "lot" per purchase with `remaining` and `expires_at`. Duplicate purchases are rejected via the
  unique (organization_id, external_ref) constraint on transactions and (account_id, idempotency_key) on the ledger.
* Redemption: the account row is locked (SELECT ... FOR UPDATE on PostgreSQL), eligibility is validated, points are
  consumed FIFO from the oldest unexpired lots, stock is decremented atomically. Idempotent via redemption key.
* Expiry: lots past `expires_at` with remaining > 0 are zeroed and an `expire` ledger entry is written.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (Customer, LoyaltyAccount, Organization, PointsLedger, Reward, RewardRedemption, Transaction)
from app.services import audit

TIER_ORDER = {"bronze": 0, "silver": 1, "gold": 2}


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def tier_for(org: Organization, lifetime: int) -> str:
    return "gold" if lifetime >= org.tier_gold_points else "silver" if lifetime >= org.tier_silver_points else "bronze"


def points_for(org: Organization, amount: float) -> int:
    return 0 if amount < org.min_purchase_for_points else int(amount * org.points_per_currency)


def lock_account(db: Session, customer_id: int, org_id: int) -> LoyaltyAccount:
    acc = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.customer_id == customer_id,
                                                 LoyaltyAccount.organization_id == org_id).with_for_update())
    if not acc:
        raise HTTPException(404, "Loyalty account not found")
    return acc


def _credit(db: Session, org: Organization, acc: LoyaltyAccount, pts: int, kind: str, key: str, at: datetime,
            txn_id: int | None = None, note: str | None = None) -> PointsLedger:
    entry = PointsLedger(organization_id=org.id, account_id=acc.id, kind=kind, points=pts, remaining=pts,
                         expires_at=at + timedelta(days=org.points_expiry_days), idempotency_key=key,
                         transaction_id=txn_id, note=note, occurred_at=at)
    db.add(entry)
    acc.balance += pts
    acc.lifetime_points += pts
    acc.tier = tier_for(org, acc.lifetime_points)
    return entry


def record_purchase(db: Session, org: Organization, customer: Customer, amount: float, external_ref: str,
                    category: str = "general", occurred_at: datetime | None = None, user_id: int | None = None,
                    commit: bool = True) -> Transaction:
    if amount <= 0:
        raise HTTPException(422, "Amount must be positive")
    at = aware(occurred_at) or now()
    if db.scalar(select(Transaction.id).where(Transaction.organization_id == org.id,
                                              Transaction.external_ref == external_ref)):
        raise HTTPException(409, f"Duplicate transaction '{external_ref}' — points already awarded")
    acc = lock_account(db, customer.id, org.id)
    pts = points_for(org, amount)
    txn = Transaction(organization_id=org.id, customer_id=customer.id, external_ref=external_ref, amount=amount,
                      category=category.lower(), occurred_at=at, points_awarded=pts)
    db.add(txn)
    try:
        db.flush()
        if pts:
            _credit(db, org, acc, pts, "earn", f"txn:{external_ref}", at, txn.id, f"Purchase {external_ref}")
        audit.log(db, org.id, user_id, "purchase.recorded", "transaction", txn.id, amount=amount, points=pts)
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError:
        db.rollback()  # concurrent duplicate lost the race to the unique constraint
        raise HTTPException(409, f"Duplicate transaction '{external_ref}' — points already awarded")
    return txn


def grant_bonus(db: Session, org: Organization, customer_id: int, pts: int, key: str, note: str,
                user_id: int | None = None) -> PointsLedger | None:
    if pts <= 0:
        raise HTTPException(422, "Bonus must be positive")
    if db.scalar(select(PointsLedger.id).join(LoyaltyAccount).where(LoyaltyAccount.customer_id == customer_id,
                                                                    PointsLedger.idempotency_key == key)):
        return None
    acc = lock_account(db, customer_id, org.id)
    e = _credit(db, org, acc, pts, "bonus", key, now(), note=note)
    audit.log(db, org.id, user_id, "points.bonus", "loyalty_account", acc.id, points=pts, note=note)
    return e


def eligibility(org: Organization, acc: LoyaltyAccount, reward: Reward) -> list[str]:
    problems = []
    if not reward.active:
        problems.append("Reward is inactive")
    if reward.valid_until and aware(reward.valid_until) < now():
        problems.append("Reward has expired")
    if reward.stock <= 0:
        problems.append("Out of stock")
    if TIER_ORDER.get(acc.tier, 0) < TIER_ORDER.get(reward.min_tier, 0):
        problems.append(f"Requires {reward.min_tier} tier (customer is {acc.tier})")
    if acc.balance < reward.points_cost:
        problems.append(f"Needs {reward.points_cost - acc.balance} more points")
    return problems


def redeem(db: Session, org: Organization, customer_id: int, reward_id: int, idempotency_key: str,
           user_id: int | None = None, campaign_id: int | None = None, at: datetime | None = None,
           commit: bool = True) -> RewardRedemption:
    existing = db.scalar(select(RewardRedemption).where(RewardRedemption.organization_id == org.id,
                                                        RewardRedemption.idempotency_key == idempotency_key))
    if existing:
        if existing.customer_id != customer_id or existing.reward_id != reward_id:
            raise HTTPException(409, "Idempotency key reused for a different redemption")
        return existing
    expire_points(db, org, customer_id=customer_id, commit=False)
    acc = lock_account(db, customer_id, org.id)
    reward = db.scalar(select(Reward).where(Reward.id == reward_id, Reward.organization_id == org.id).with_for_update())
    if not reward:
        raise HTTPException(404, "Reward not found")
    problems = eligibility(org, acc, reward)
    if problems:
        db.rollback()
        raise HTTPException(422, "Not eligible: " + "; ".join(problems))
    at = at or now()
    # Atomic conditional stock decrement guards against concurrent over-redemption.
    res = db.execute(update(Reward).where(Reward.id == reward.id, Reward.stock > 0).values(stock=Reward.stock - 1))
    if res.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Reward just went out of stock")
    red = RewardRedemption(organization_id=org.id, customer_id=customer_id, reward_id=reward.id,
                           points_spent=reward.points_cost, idempotency_key=idempotency_key, campaign_id=campaign_id,
                           occurred_at=at)
    db.add(red)
    db.flush()
    need = reward.points_cost
    lots = db.scalars(select(PointsLedger).where(PointsLedger.account_id == acc.id, PointsLedger.remaining > 0)
                      .order_by(PointsLedger.expires_at.asc(), PointsLedger.id.asc()).with_for_update()).all()
    for lot in lots:
        take = min(lot.remaining, need)
        lot.remaining -= take
        need -= take
        if need == 0:
            break
    if need:
        db.rollback()
        raise HTTPException(409, "Ledger inconsistency: insufficient unexpired points")
    db.add(PointsLedger(organization_id=org.id, account_id=acc.id, kind="redeem", points=-reward.points_cost,
                        remaining=0, idempotency_key=f"redeem:{idempotency_key}", redemption_id=red.id,
                        note=f"Redeemed {reward.name}", occurred_at=at))
    acc.balance -= reward.points_cost
    audit.log(db, org.id, user_id, "reward.redeemed", "reward_redemption", red.id, reward_id=reward.id,
              points=reward.points_cost, customer_id=customer_id)
    if commit:
        db.commit()
    else:
        db.flush()
    return red


def expire_points(db: Session, org: Organization, customer_id: int | None = None, as_of: datetime | None = None,
                  commit: bool = True) -> int:
    as_of = as_of or now()
    stmt = (select(PointsLedger, LoyaltyAccount).join(LoyaltyAccount)
            .where(PointsLedger.organization_id == org.id, PointsLedger.remaining > 0,
                   PointsLedger.expires_at <= as_of))
    if customer_id:
        stmt = stmt.where(LoyaltyAccount.customer_id == customer_id)
    total = 0
    for lot, acc in db.execute(stmt).all():
        pts = lot.remaining
        lot.remaining = 0
        acc.balance -= pts
        total += pts
        db.add(PointsLedger(organization_id=org.id, account_id=acc.id, kind="expire", points=-pts, remaining=0,
                            idempotency_key=f"expire:{lot.id}", note=f"Lot #{lot.id} expired", occurred_at=as_of))
    if total:
        audit.log(db, org.id, None, "points.expired", "organization", org.id, points=total)
    if commit:
        db.commit()
    else:
        db.flush()
    return total
