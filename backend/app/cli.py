"""python -m app.cli seed-synthetic [n]   # create the SYNTHETIC demo org (login demo@loyaltyiq.demo / demo12345)
python -m app.cli expire                  # run the points-expiry job for every organization (schedule daily)"""
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Organization, User
from app.services import points, synthetic


def main(argv):
    with SessionLocal() as db:
        if argv and argv[0] == "seed-synthetic":
            if db.scalar(select(User).where(User.email == "demo@loyaltyiq.demo")):
                print("synthetic demo already exists")
                return
            org = synthetic.generate(db, int(argv[1]) if len(argv) > 1 else 300)
            print(f"created synthetic org #{org.id}: {org.name}")
        elif argv and argv[0] == "expire":
            for org in db.scalars(select(Organization)).all():
                print(org.name, points.expire_points(db, org))
        else:
            print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
