"""RFM segmentation + optional K-means clustering.

1. Features per customer (pandas): recency_days, frequency, monetary, redemptions, engagement events, tenure.
2. RFM scores 1-5 by percentile rank within the organization (robust for small n; ties averaged).
3. Rule-based segments, evaluated in order (documented in SEGMENT_RULES and returned to the UI):
     new          – joined/first purchase ≤ 30 days ago and frequency ≤ 2
     inactive     – no purchase ever, or recency > 180 days
     high_value   – M = 5 and F ≥ 4 and R ≥ 3
     at_risk      – (R ≤ 2 or recency > 90 days) and (F ≥ 3 or M ≥ 3)   (used to buy, slipping away)
     loyal        – F ≥ 3 and R ≥ 3 and recency ≤ 90 days
     regular      – everyone else
4. K-means (scikit-learn, k = min(4, n)) on standardized log features, reported alongside the rule segments.
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.models import CampaignEvent, Customer, CustomerSegment, RewardRedemption, Transaction

SEGMENT_RULES = [
    ("new", "Joined or first purchased within 30 days, ≤ 2 purchases"),
    ("inactive", "No purchases, or last purchase more than 180 days ago"),
    ("high_value", "Top monetary quintile (M=5), frequent (F≥4) and recent (R≥3)"),
    ("at_risk", "Previously valuable (F≥3 or M≥3) but slipping away (R≤2 or no purchase in 90 days)"),
    ("loyal", "Purchases often (F≥3) and recently (R≥3, within 90 days)"),
    ("regular", "Everyone else"),
]
SEGMENTS = [s for s, _ in SEGMENT_RULES]


def _score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    if len(series) == 1:
        return pd.Series([3], index=series.index)
    pct = series.rank(pct=True, method="average", ascending=higher_is_better)
    return np.ceil(pct * 5).clip(1, 5).astype(int)


def assign(row) -> tuple[str, str]:
    if row.tenure_days <= 30 and row.frequency <= 2:
        return "new", f"Joined {int(row.tenure_days)} days ago with {int(row.frequency)} purchase(s)"
    if row.frequency == 0 or row.recency_days > 180:
        return "inactive", ("No purchases yet" if row.frequency == 0 else f"Last purchase {int(row.recency_days)} days ago")
    if row.m_score == 5 and row.f_score >= 4 and row.r_score >= 3:
        return "high_value", f"Spend ₹{row.monetary:,.0f} (top 20%), {int(row.frequency)} purchases, recent"
    if (row.r_score <= 2 or row.recency_days > 90) and (row.f_score >= 3 or row.m_score >= 3):
        return "at_risk", f"Good history ({int(row.frequency)} purchases) but last seen {int(row.recency_days)} days ago"
    if row.f_score >= 3 and row.r_score >= 3 and row.recency_days <= 90:
        return "loyal", f"{int(row.frequency)} purchases, last {int(row.recency_days)} days ago"
    return "regular", f"R{row.r_score} F{row.f_score} M{row.m_score}"


def features(db: Session, org_id: int, as_of: datetime | None = None) -> pd.DataFrame:
    as_of = as_of or datetime.now(timezone.utc)
    cust = pd.DataFrame(db.execute(select(Customer.id, Customer.joined_at).where(Customer.organization_id == org_id)).all(),
                        columns=["customer_id", "joined_at"])
    if cust.empty:
        return cust
    tx = pd.DataFrame(db.execute(select(Transaction.customer_id, func.max(Transaction.occurred_at),
                                        func.min(Transaction.occurred_at), func.count(), func.sum(Transaction.amount))
                                 .where(Transaction.organization_id == org_id).group_by(Transaction.customer_id)).all(),
                      columns=["customer_id", "last", "first", "frequency", "monetary"])
    red = pd.DataFrame(db.execute(select(RewardRedemption.customer_id, func.count()).where(
        RewardRedemption.organization_id == org_id).group_by(RewardRedemption.customer_id)).all(),
        columns=["customer_id", "redemptions"])
    ev = pd.DataFrame(db.execute(select(CampaignEvent.customer_id, func.count()).join(Customer).where(
        Customer.organization_id == org_id, CampaignEvent.kind.in_(["opened", "clicked", "redeemed"]))
        .group_by(CampaignEvent.customer_id)).all(), columns=["customer_id", "engagement_events"])
    df = cust.merge(tx, how="left", on="customer_id").merge(red, how="left", on="customer_id") \
             .merge(ev, how="left", on="customer_id")
    def days(col):
        return df[col].apply(lambda d: (as_of - (d if d.tzinfo else d.replace(tzinfo=timezone.utc))).days
                             if pd.notna(d) else np.nan)
    df["recency_days"] = days("last").fillna(9999)
    start = df["first"].where(df["first"].notna() & (df["first"] < df["joined_at"]), df["joined_at"])
    df["tenure_days"] = start.apply(lambda d: (as_of - (d if d.tzinfo else d.replace(tzinfo=timezone.utc))).days)
    for col in ("frequency", "monetary", "redemptions", "engagement_events"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["frequency"] = df["frequency"].astype(int)
    return df


def run(db: Session, org_id: int, as_of: datetime | None = None, k: int = 4) -> dict:
    df = features(db, org_id, as_of)
    db.execute(delete(CustomerSegment).where(CustomerSegment.organization_id == org_id))
    if df.empty:
        db.commit()
        return {"customers": 0, "segments": {}, "clusters": []}
    buyers = df["frequency"] > 0
    df["r_score"], df["f_score"], df["m_score"] = 1, 1, 1
    if buyers.any():
        df.loc[buyers, "r_score"] = _score(df.loc[buyers, "recency_days"], higher_is_better=False)
        df.loc[buyers, "f_score"] = _score(df.loc[buyers, "frequency"])
        df.loc[buyers, "m_score"] = _score(df.loc[buyers, "monetary"])
    seg = df.apply(assign, axis=1, result_type="expand")
    df["segment"], df["reason"] = seg[0], seg[1]

    clusters_info = []
    df["cluster"] = None
    if len(df) >= 4:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        X = np.log1p(df[["recency_days", "frequency", "monetary", "redemptions"]].clip(upper=3650).values)
        Xs = StandardScaler().fit_transform(X)
        kk = min(k, len(df))
        km = KMeans(n_clusters=kk, n_init=10, random_state=42).fit(Xs)
        df["cluster"] = km.labels_
        for c in range(kk):
            part = df[df.cluster == c]
            clusters_info.append({"cluster": c, "size": int(len(part)),
                                  "avg_recency_days": round(float(part.recency_days.clip(upper=3650).mean()), 1),
                                  "avg_frequency": round(float(part.frequency.mean()), 2),
                                  "avg_monetary": round(float(part.monetary.mean()), 2),
                                  "dominant_segment": part.segment.mode().iat[0]})
    for r in df.itertuples():
        db.add(CustomerSegment(organization_id=org_id, customer_id=int(r.customer_id), segment=r.segment,
                               recency_days=float(min(r.recency_days, 9999)), frequency=int(r.frequency),
                               monetary=float(r.monetary), r_score=int(r.r_score), f_score=int(r.f_score),
                               m_score=int(r.m_score), redemptions=int(r.redemptions),
                               engagement_events=int(r.engagement_events),
                               cluster=None if r.cluster is None or pd.isna(r.cluster) else int(r.cluster),
                               reason=r.reason))
    db.commit()
    return {"customers": int(len(df)), "segments": df.segment.value_counts().to_dict(), "clusters": clusters_info}


def summary(db: Session, org_id: int) -> list[dict]:
    rows = db.execute(select(CustomerSegment.segment, func.count(), func.avg(case((CustomerSegment.recency_days < 9999, CustomerSegment.recency_days))),
                             func.avg(CustomerSegment.frequency), func.avg(CustomerSegment.monetary),
                             func.avg(CustomerSegment.redemptions))
                      .where(CustomerSegment.organization_id == org_id).group_by(CustomerSegment.segment)).all()
    desc = dict(SEGMENT_RULES)
    by = {r[0]: r for r in rows}
    return [{"segment": s, "rule": desc[s], "customers": by[s][1] if s in by else 0,
             "avg_recency_days": round(by[s][2], 1) if s in by and by[s][2] is not None else None,
             "avg_frequency": round(by[s][3], 2) if s in by else None,
             "avg_monetary": round(by[s][4], 2) if s in by else None,
             "avg_redemptions": round(by[s][5], 2) if s in by else None} for s in SEGMENTS]
