import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { useApi } from "../lib/useApi";
import { RewardRec, SEGMENTS } from "../types";

type Row = { customer_id: number; name: string; segment: string; balance: number; tier: string; top_reward: RewardRec | null };

export default function Recommendations() {
  const [seg, setSeg] = useState("at_risk");
  const { data, loading, error } = useApi<Row[]>(`/api/recommendations?segment=${seg}&limit=40`);
  return (
    <>
      <PageHeader title="AI reward recommendations"><select className="input" value={seg} onChange={(e) => setSeg(e.target.value)}>{SEGMENTS.map((s) => <option key={s}>{s}</option>)}</select></PageHeader>
      <p className="mb-4 text-sm text-slate-500">Best eligible reward per customer, ranked by spend affinity, stated preferences, segment rules, affordability and redemption history. Only eligible rewards are considered (tier, stock, validity).</p>
      {loading ? <Spinner /> : error ? <ErrorBox msg={error} /> : !data?.length ? <Empty title="No customers in this segment" hint="Run segmentation first." /> :
        <div className="card overflow-x-auto p-0"><table className="w-full"><thead className="bg-slate-50"><tr><th className="th">Customer</th><th className="th">Tier</th><th className="th">Balance</th><th className="th">Recommended reward</th><th className="th">Why</th></tr></thead>
          <tbody className="divide-y">{data.map((r) => <tr key={r.customer_id}><td className="td"><Link className="text-brand-700" to={`/app/customers/${r.customer_id}`}>{r.name}</Link></td><td className="td">{r.tier}</td><td className="td">{r.balance}</td>
            <td className="td">{r.top_reward ? <>{r.top_reward.name} <span className="text-xs text-slate-500">({r.top_reward.points_cost} pts)</span> {r.top_reward.affordable ? <Badge tone="green">affordable</Badge> : <Badge>saving up</Badge>}</> : "—"}</td>
            <td className="td text-xs">{r.top_reward?.reasons.join(" · ")}</td></tr>)}</tbody></table></div>}
    </>
  );
}
