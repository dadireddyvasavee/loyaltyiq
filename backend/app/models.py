from datetime import datetime

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TS:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Organization(TS, Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    # loyalty rules (deterministic, configurable)
    points_per_currency: Mapped[float] = mapped_column(Float, default=0.1)   # 1 pt per ₹10
    min_purchase_for_points: Mapped[float] = mapped_column(Float, default=0)
    points_expiry_days: Mapped[int] = mapped_column(Integer, default=365)
    tier_silver_points: Mapped[int] = mapped_column(Integer, default=1000)  # lifetime points thresholds
    tier_gold_points: Mapped[int] = mapped_column(Integer, default=5000)
    welcome_bonus: Mapped[int] = mapped_column(Integer, default=0)


class User(TS, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="owner")  # owner|admin|analyst


class Customer(TS, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "email"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    preferred_categories: Mapped[list] = mapped_column(JSON, default=list)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    account: Mapped["LoyaltyAccount"] = relationship(back_populates="customer", uselist=False, lazy="joined")


class LoyaltyAccount(TS, Base):
    __tablename__ = "loyalty_accounts"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_balance_nonneg"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), unique=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_points: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[str] = mapped_column(String(20), default="bronze")
    customer: Mapped[Customer] = relationship(back_populates="account")


class Transaction(TS, Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("organization_id", "external_ref", name="uq_txn_ref"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    external_ref: Mapped[str] = mapped_column(String(100))  # idempotency key (POS/order id)
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(50), default="general", index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)


class PointsLedger(TS, Base):
    __tablename__ = "points_ledger"
    __table_args__ = (UniqueConstraint("account_id", "idempotency_key", name="uq_ledger_idem"),
                      Index("ix_ledger_fifo", "account_id", "expires_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("loyalty_accounts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # earn|redeem|expire|adjust|bonus
    points: Mapped[int] = mapped_column(Integer)  # signed
    remaining: Mapped[int] = mapped_column(Integer, default=0)  # unspent points of an earn lot (FIFO)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    redemption_id: Mapped[int | None] = mapped_column(ForeignKey("reward_redemptions.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Reward(TS, Base):
    __tablename__ = "rewards"
    __table_args__ = (CheckConstraint("points_cost > 0", name="ck_cost_pos"), CheckConstraint("stock >= 0", name="ck_stock"))
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), default="general")
    points_cost: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=100)
    min_tier: Mapped[str] = mapped_column(String(20), default="bronze")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RewardRedemption(TS, Base):
    __tablename__ = "reward_redemptions"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_redeem_idem"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    reward_id: Mapped[int] = mapped_column(ForeignKey("rewards.id", ondelete="CASCADE"), index=True)
    points_spent: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reward: Mapped[Reward] = relationship(lazy="joined")


class CustomerSegment(TS, Base):
    __tablename__ = "customer_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), unique=True)
    segment: Mapped[str] = mapped_column(String(30), index=True)
    recency_days: Mapped[float] = mapped_column(Float)
    frequency: Mapped[int] = mapped_column(Integer)
    monetary: Mapped[float] = mapped_column(Float)
    r_score: Mapped[int] = mapped_column(Integer)
    f_score: Mapped[int] = mapped_column(Integer)
    m_score: Mapped[int] = mapped_column(Integer)
    redemptions: Mapped[int] = mapped_column(Integer, default=0)
    engagement_events: Mapped[int] = mapped_column(Integer, default=0)
    cluster: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))


class Campaign(TS, Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str] = mapped_column(Text)
    segment: Mapped[str] = mapped_column(String(30))
    message_template: Mapped[str] = mapped_column(Text)
    ideas: Mapped[list] = mapped_column(JSON, default=list)
    reward_id: Mapped[int | None] = mapped_column(ForeignKey("rewards.id", ondelete="SET NULL"))
    bonus_points: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft|approved|active|completed
    generated_by: Mapped[str] = mapped_column(String(20), default="manual")  # manual|llm
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reward: Mapped[Reward | None] = relationship(lazy="joined")


class CampaignRecipient(TS, Base):
    __tablename__ = "campaign_recipients"
    __table_args__ = (UniqueConstraint("campaign_id", "customer_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text)


class CampaignEvent(TS, Base):
    __tablename__ = "campaign_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # sent|opened|clicked|redeemed


class AuditLog(TS, Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
