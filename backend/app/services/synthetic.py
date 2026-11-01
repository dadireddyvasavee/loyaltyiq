"""SYNTHETIC demo dataset generator. Every record belongs to an organization flagged is_synthetic=True whose name
ends with "(SYNTHETIC DEMO)". Behavioural archetypes generate realistic-looking but entirely fictional histories.
All points are produced through the real points engine so ledger invariants hold."""
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Customer, LoyaltyAccount, Organization, Reward, User
from app.services import points, segmentation

FIRST = ["Aarav", "Diya", "Kabir", "Ananya", "Rohan", "Isha", "Vihaan", "Meera", "Arjun", "Saanvi", "Kiran", "Priya",
         "Rahul", "Sneha", "Aditya", "Neha", "Karthik", "Pooja", "Siddharth", "Lakshmi"]
LAST = ["Sharma", "Reddy", "Iyer", "Patel", "Nair", "Gupta", "Rao", "Khan", "Das", "Menon", "Joshi", "Verma"]
CATS = ["coffee", "bakery", "merchandise", "breakfast"]
REWARDS = [("Free regular coffee", "coffee", 150, "bronze"), ("Free croissant", "bakery", 120, "bronze"),
           ("Breakfast combo", "breakfast", 400, "bronze"), ("Branded tumbler", "merchandise", 900, "silver"),
           ("Coffee tasting session", "experience", 2000, "gold"), ("Any large beverage", "coffee", 250, "bronze"),
           ("Bag of house beans 250g", "merchandise", 1200, "silver")]
# archetype: (share, purchases range, avg ticket, days-since-last range, tenure days range)
ARCH = {"champion": (0.12, (25, 60), 650, (0, 20), (300, 540)), "regular": (0.38, (6, 20), 350, (0, 60), (120, 540)),
        "fading": (0.2, (8, 25), 450, (75, 170), (250, 540)), "lapsed": (0.15, (2, 8), 300, (200, 400), (300, 540)),
        "newbie": (0.15, (0, 2), 300, (0, 25), (1, 28))}


def generate(db: Session, n_customers: int = 300, seed: int = 42) -> Organization:
    rnd = random.Random(seed)
    org = Organization(name="Brew & Bean Café (SYNTHETIC DEMO)", is_synthetic=True, points_per_currency=0.1,
                       points_expiry_days=365, tier_silver_points=800, tier_gold_points=3000)
    db.add(org)
    db.flush()
    db.add(User(organization_id=org.id, email="demo@loyaltyiq.demo", full_name="Demo Owner",
                password_hash=hash_password("demo12345"), role="owner"))
    db.add(User(organization_id=org.id, email="analyst@loyaltyiq.demo", full_name="Demo Analyst",
                password_hash=hash_password("demo12345"), role="analyst"))
    rewards = [Reward(organization_id=org.id, name=n, category=c, points_cost=p, min_tier=t, stock=rnd.randint(40, 300),
                      description=f"Synthetic demo reward: {n}") for n, c, p, t in REWARDS]
    db.add_all(rewards)
    db.flush()
    now = points.now()
    archs = list(ARCH)
    weights = [ARCH[a][0] for a in archs]
    ref = 0
    for i in range(n_customers):
        a = rnd.choices(archs, weights)[0]
        _, (fmin, fmax), ticket, (lmin, lmax), (tmin, tmax) = ARCH[a]
        tenure = rnd.randint(tmin, tmax)
        fav = rnd.sample(CATS, 2)
        c = Customer(organization_id=org.id, first_name=rnd.choice(FIRST), last_name=rnd.choice(LAST),
                     email=f"customer{i+1}@synthetic.example", preferred_categories=fav[:1],
                     joined_at=now - timedelta(days=tenure))
        c.account = LoyaltyAccount(organization_id=org.id)
        db.add(c)
        db.flush()
        n = rnd.randint(fmin, fmax)
        last = rnd.randint(lmin, min(lmax, tenure)) if n else tenure
        days = sorted({rnd.randint(last, tenure) for _ in range(n)}, reverse=True)
        for d in days:
            ref += 1
            cat = rnd.choices(fav + CATS, [5, 3, 1, 1, 1, 1])[0]
            points.record_purchase(db, org, c, round(max(80, rnd.gauss(ticket, ticket * 0.35)), 2), f"SYN-{ref:06d}",
                                   cat, now - timedelta(days=d, hours=rnd.randint(7, 20)), commit=False)
        # some redemptions, chronologically after earning
        points.expire_points(db, org, customer_id=c.id, commit=False)
        affordable = [r for r in rewards if r.points_cost <= c.account.balance and r.min_tier == "bronze"]
        if affordable and rnd.random() < (0.7 if a in ("champion", "regular") else 0.3):
            r = rnd.choice(affordable)
            points.redeem(db, org, c.id, r.id, f"SYN-RED-{c.id}", at=now - timedelta(days=max(0, last - 1)), commit=False)
    points.expire_points(db, org, commit=False)
    db.commit()
    segmentation.run(db, org.id)
    return org
