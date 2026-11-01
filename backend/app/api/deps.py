import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models import Organization, User

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        uid = int(decode_token(cred.credentials)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User not found")
    return user


def current_org(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Organization:
    return db.get(Organization, user.organization_id)


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role: {' or '.join(roles)}")
        return user
    return dep


writer = require("owner", "admin")
owner_only = require("owner")


def scoped(db: Session, model, obj_id: int, org_id: int, name: str):
    """Fetch an entity only if it belongs to the caller's organization (404 otherwise — no existence leak)."""
    obj = db.get(model, obj_id)
    if not obj or obj.organization_id != org_id:
        raise HTTPException(404, f"{name} not found")
    return obj
