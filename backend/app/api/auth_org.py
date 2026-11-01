from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org, current_user, owner_only, require, writer
from app.core.db import get_db
from app.core.security import create_token, hash_password, verify_password
from app.models import AuditLog, Organization, User
from app.schemas import LoginIn, OrgIO, OrgOut, RegisterIn, TokenOut, UserCreate, UserOut
from app.services import audit

router = APIRouter(prefix="/api", tags=["auth & organization"])


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Creates a new organization and its owner account."""
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    org = Organization(name=body.organization_name)
    db.add(org)
    db.flush()
    u = User(organization_id=org.id, email=body.email.lower(), full_name=body.full_name,
             password_hash=hash_password(body.password), role="owner")
    db.add(u)
    db.flush()
    audit.log(db, org.id, u.id, "organization.created", "organization", org.id)
    db.commit()
    return TokenOut(access_token=create_token(str(u.id)))


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return TokenOut(access_token=create_token(str(u.id)))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/org", response_model=OrgOut)
def get_org(org: Organization = Depends(current_org)):
    return org


@router.put("/org", response_model=OrgOut)
def put_org(body: OrgIO, db: Session = Depends(get_db), org: Organization = Depends(current_org),
            user: User = Depends(writer)):
    if body.tier_gold_points <= body.tier_silver_points:
        raise HTTPException(422, "Gold threshold must exceed silver threshold")
    before = OrgIO.model_validate(org).model_dump()
    for k, v in body.model_dump().items():
        setattr(org, k, v)
    audit.log(db, org.id, user.id, "loyalty_rules.updated", "organization", org.id, before=before, after=body.model_dump())
    db.commit()
    return org


@router.get("/org/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(User).where(User.organization_id == user.organization_id)).all()


@router.post("/org/users", response_model=UserOut, status_code=201)
def add_user(body: UserCreate, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(organization_id=user.organization_id, email=body.email.lower(), full_name=body.full_name,
             password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    db.flush()
    audit.log(db, user.organization_id, user.id, "user.created", "user", u.id, role=body.role)
    db.commit()
    return u


@router.get("/audit")
def audit_logs(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require("owner", "admin"))):
    rows = db.scalars(select(AuditLog).where(AuditLog.organization_id == user.organization_id)
                      .order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return [{"id": a.id, "at": a.created_at, "user_id": a.user_id, "action": a.action, "entity": a.entity,
             "entity_id": a.entity_id, "detail": a.detail} for a in rows]
