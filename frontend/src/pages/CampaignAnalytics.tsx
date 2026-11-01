import { Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { useApi } from "../lib/useApi";
import { CampaignMetrics, inr, pct, SegmentRow } from "../types";

type Dash = { campaigns: CampaignMetrics[]; points_issued: number; points_redeemed: number; points_utilization: number | null };
type SegPerf = SegmentRow & { campaigns: number; campaign_reach: number; campaign_redemption_rate: number | null; campaign_retention_rate: number | null };

export default function CampaignAnalytics() {
  const d = useApi<Dash>("/api/analytics/dashboard");
  const s = useApi<SegPerf[]>("/api/analytics/segments");
  if (d.loading || s.loading) return <Spinner />;
  if (d.error) return <ErrorBox msg={d.error} />;
  const c = d.data!.campaigns;
  const chart = c.map((m) => ({ name: m.name, Reach: m.reach, Opened: m.opened, Redeemed: m.redeemers, "Purchased again": m.purchasers_after }));
  return (
    <>
      <PageHeader title="Campaign analytics" />
      <div className="card mb-6"><p className="label">Funnel per campaign</p>{c.length ? <ResponsiveContainer height={280}><BarChart data={chart}><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend /><Bar dataKey="Reach" fill="#94a3b8" /><Bar dataKey="Opened" fill="#06b6d4" /><Bar dataKey="Redeemed" fill="#ea580c" /><Bar dataKey="Purchased again" fill="#10b981" /></BarChart></ResponsiveContainer> : <Empty title="No activated campaigns yet" />}</div>
      {c.length > 0 && <div className="card mb-6 overflow-x-auto p-0"><table className="w-full"><thead className="bg-slate-50"><tr>{["Campaign", "Segment", "Status", "Reach", "Open rate", "Click rate", "Redemption rate", "Retention rate"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody className="divide-y">{c.map((m) => <tr key={m.campaign_id}><td className="td">{m.name}</td><td className="td">{m.segment}</td><td className="td">{m.status}</td><td className="td">{m.reach}</td><td className="td">{pct(m.open_rate)}</td><td className="td">{pct(m.click_rate)}</td><td className="td">{pct(m.redemption_rate)}</td><td className="td">{pct(m.retention_rate)}</td></tr>)}</tbody></table></div>}
      <div className="card mb-6 overflow-x-auto p-0"><p className="label p-4 pb-0">Segment performance</p><table className="w-full"><thead className="bg-slate-50"><tr>{["Segment", "Customers", "Avg spend", "Avg redemptions", "Campaigns", "Campaign reach", "Redemption rate", "Retention rate"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody className="divide-y">{s.data?.map((r) => <tr key={r.segment}><td className="td">{r.segment}</td><td className="td">{r.customers}</td><td className="td">{r.avg_monetary !== null ? inr(r.avg_monetary) : "—"}</td><td className="td">{r.avg_redemptions ?? "—"}</td><td className="td">{r.campaigns}</td><td className="td">{r.campaign_reach}</td><td className="td">{pct(r.campaign_redemption_rate)}</td><td className="td">{pct(r.campaign_retention_rate)}</td></tr>)}</tbody></table></div>
      <div className="card text-xs text-slate-500"><p className="label">Metric definitions</p><ul className="space-y-1">{c[0] ? Object.entries(c[0].definitions).map(([k, v]) => <li key={k}><b>{k}</b>: {v}</li>) : <li>Points utilization = points redeemed ÷ points issued ({pct(d.data!.points_utilization)}).</li>}</ul></div>
    </>
  );
}
