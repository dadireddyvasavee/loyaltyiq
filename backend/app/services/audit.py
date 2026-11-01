from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, org_id: int, user_id: int | None, action: str, entity: str, entity_id: int | None = None,
        **detail) -> None:
    db.add(AuditLog(organization_id=org_id, user_id=user_id, action=action, entity=entity, entity_id=entity_id,
                    detail={k: (v if isinstance(v, (int, float, str, bool, type(None), list, dict)) else str(v))
                            for k, v in detail.items()}))
