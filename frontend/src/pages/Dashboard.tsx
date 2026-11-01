import { Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorBox, PageHeader, Spinner, Stat } from "../components/ui";
import { useApi } from "../lib/useApi";
import { CampaignMetrics, pct, SEG_COLORS } from "../types";
import SyntheticBanner from "./SyntheticBanner";

type Dash = { total_customers: number; active_members_90d: number; points_issued: number; points_redeemed: number; points_expired: number; points_outstanding: number;
  points_utilization: number | null; segment_distribution: Record<string, number>; tier_distribution: Record<string, number>;
  top_rewards: { name: string; redemptions: number; points: number }[]; engagement_trend: { month: string; transactions: number; revenue: number; active_customers: number }[]; campaigns: CampaignMetrics[] };

export default function Dashboard() {
  const { data: d, loading, error } = useApi<Dash>("/api/analytics/dashboard");
  if (loading) return <Spinner />;
  if (error || !d) return <ErrorBox msg={error ?? "No data"} />;
  const seg = Object.entries(d.segment_distribution).map(([name, value]) => ({ name, value }));
  return (
    <>
      <SyntheticBanner />
      <PageHeader title="Business dashboard" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total customers" value={d.total_customers.toLocaleString()} />
        <Stat label="Active members (90d)" value={d.active_members_90d.toLocaleString()} sub={d.total_customers ? `${pct(d.active_members_90d / d.total_customers)} of members` : undefined} />
        <Stat label="Points issued" value={d.points_issued.toLocaleString()} sub={`${d.points_outstanding.toLocaleString()} outstanding · ${d.points_expired.toLocaleString()} expired`} />
        <Stat label="Points redeemed" value={d.points_redeemed.toLocaleString()} sub={`Utilization ${pct(d.points_utilization)}`} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2"><p className="label">Customer engagement trend (12 months)</p>
          {d.engagement_trend.length ? <ResponsiveContainer height={260}><LineChart data={d.engagement_trend}><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend /><Line dataKey="active_customers" name="Active customers" stroke="#ea580c" /><Line dataKey="transactions" name="Transactions" stroke="#64748b" /></LineChart></ResponsiveContainer> : <Empty title="No transactions yet" />}</div>
        <div className="card"><p className="label">Segment distribution</p>
          {seg.length ? <ResponsiveContainer height={260}><PieChart><Pie data={seg} dataKey="value" nameKey="name" innerRadius={50} outerRadius={90}>{seg.map((s) => <Cell key={s.name} fill={SEG_COLORS[s.name] ?? "#94a3b8"} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer> : <Empty title="Run segmentation" />}</div>
        <div className="card"><p className="label">Top-performing rewards</p>
          {d.top_rewards.length ? <ResponsiveContainer height={240}><BarChart data={d.top_rewards} layout="vertical"><XAxis type="number" fontSize={11} /><YAxis type="category" dataKey="name" width={130} fontSize={11} /><Tooltip /><Bar dataKey="redemptions" fill="#ea580c" /></BarChart></ResponsiveContainer> : <Empty title="No redemptions yet" />}</div>
        <div className="card lg:col-span-2"><p className="label">Campaign performance</p>
          {d.campaigns.length ? <table className="w-full"><thead><tr><th className="th">Campaign</th><th className="th">Segment</th><th className="th">Reach</th><th className="th">Redemption</th><th className="th">Retention</th></tr></thead>
            <tbody className="divide-y">{d.campaigns.map((c) => <tr key={c.campaign_id}><td className="td">{c.name}</td><td className="td">{c.segment}</td><td className="td">{c.reach}</td><td className="td">{pct(c.redemption_rate)}</td><td className="td">{pct(c.retention_rate)}</td></tr>)}</tbody></table> : <Empty title="No active campaigns" hint="Create one in the Campaign builder." />}</div>
      </div>
    </>
  );
}
