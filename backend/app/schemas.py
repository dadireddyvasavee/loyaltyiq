from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    organization_name: str = Field(min_length=2, max_length=255)
    full_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    organization_id: int


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: str = Field(pattern="^(admin|analyst)$")


class OrgIO(ORM):
    name: str = Field(min_length=2)
    points_per_currency: float = Field(gt=0, le=10)
    min_purchase_for_points: float = Field(ge=0)
    points_expiry_days: int = Field(ge=1, le=3650)
    tier_silver_points: int = Field(ge=1)
    tier_gold_points: int = Field(ge=1)
    welcome_bonus: int = Field(ge=0, le=10000)


class OrgOut(OrgIO):
    id: int
    is_synthetic: bool


class AccountOut(ORM):
    balance: int
    lifetime_points: int
    tier: str


class CustomerIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = ""
    email: EmailStr
    phone: str | None = None
    preferred_categories: list[str] = []


class CustomerOut(ORM):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None
    preferred_categories: list[str]
    joined_at: datetime
    account: AccountOut | None
    segment: str | None = None


class PurchaseIn(BaseModel):
    amount: float = Field(gt=0, le=10_000_000)
    external_ref: str = Field(min_length=1, max_length=100)
    category: str = "general"
    occurred_at: datetime | None = None


class RedeemIn(BaseModel):
    reward_id: int
    idempotency_key: str = Field(min_length=6, max_length=120)
    campaign_id: int | None = None


class RewardIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    category: str = "general"
    points_cost: int = Field(gt=0)
    stock: int = Field(ge=0)
    min_tier: str = Field("bronze", pattern="^(bronze|silver|gold)$")
    active: bool = True
    valid_until: datetime | None = None


class RewardOut(ORM, RewardIn):
    id: int


class CampaignGenIn(BaseModel):
    objective: str = Field(min_length=5, max_length=500)
    segment: str
    tone: str = "warm and friendly"


class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    objective: str
    segment: str
    message_template: str = Field(min_length=5, max_length=600)
    ideas: list[str] = []
    reward_id: int | None = None
    bonus_points: int = Field(0, ge=0, le=1000)
    generated_by: str = Field("manual", pattern="^(manual|llm)$")


class CampaignOut(ORM):
    id: int
    name: str
    objective: str
    segment: str
    message_template: str
    ideas: list[str]
    reward_id: int | None
    bonus_points: int
    status: str
    generated_by: str
    created_by: int
    approved_by: int | None
    activated_at: datetime | None
    created_at: datetime


class EventIn(BaseModel):
    customer_id: int
    kind: str = Field(pattern="^(opened|clicked)$")
