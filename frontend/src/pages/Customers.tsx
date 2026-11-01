import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useCanWrite } from "../lib/role";
import { useApi } from "../lib/useApi";
import { Customer, SEGMENTS } from "../types";

export default function Customers() {
  const canWrite = useCanWrite();
  const [q, setQ] = useState(""); const [seg, setSeg] = useState(""); const [tier, setTier] = useState("");
  const p = new URLSearchParams(); if (q) p.set("q", q); if (seg) p.set("segment", seg); if (tier) p.set("tier", tier);
  const { data, loading, error, reload } = useApi<Customer[]>(`/api/customers?${p}`);
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", phone: "", cats: "" });
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    try { await api("/api/customers", { method: "POST", json: { first_name: f.first_name, last_name: f.last_name, email: f.email, phone: f.phone || null, preferred_categories: f.cats.split(",").map((s) => s.trim()).filter(Boolean) } }); setShow(false); reload(); }
    catch (x) { setErr((x as Error).message); }
  };
  return (
    <>
      <PageHeader title="Customers">{canWrite && <button className="btn" onClick={() => setShow(!show)}>{show ? "Close" : "Register customer"}</button>}</PageHeader>
      {show && <form onSubmit={submit} className="card mb-4 grid gap-3 md:grid-cols-3">{err && <div className="md:col-span-3"><ErrorBox msg={err} /></div>}
        {(["first_name", "last_name", "email", "phone", "cats"] as const).map((k) => <label key={k}><span className="label">{k === "cats" ? "Preferred categories (comma)" : k.replace("_", " ")}</span><input className="input" required={k === "first_name" || k === "email"} type={k === "email" ? "email" : "text"} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>)}
        <div className="flex items-end"><button className="btn">Save</button></div></form>}
      <div className="mb-4 flex flex-wrap gap-2"><input className="input max-w-xs" placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input max-w-[12rem]" value={seg} onChange={(e) => setSeg(e.target.value)}><option value="">All segments</option>{SEGMENTS.map((s) => <option key={s}>{s}</option>)}</select>
        <select className="input max-w-[10rem]" value={tier} onChange={(e) => setTier(e.target.value)}><option value="">All tiers</option>{["bronze", "silver", "gold"].map((t) => <option key={t}>{t}</option>)}</select></div>
      {loading ? <Spinner /> : error ? <ErrorBox msg={error} /> : !data?.length ? <Empty title="No customers" /> :
        <div className="card overflow-x-auto p-0"><table className="w-full"><thead className="bg-slate-50"><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Tier</th><th className="th">Balance</th><th className="th">Lifetime pts</th><th className="th">Segment</th></tr></thead>
          <tbody className="divide-y">{data.map((c) => <tr key={c.id} className="hover:bg-slate-50"><td className="td"><Link className="font-medium text-brand-700" to={`/app/customers/${c.id}`}>{c.first_name} {c.last_name}</Link></td><td className="td">{c.email}</td>
            <td className="td"><Badge tone={c.account?.tier === "gold" ? "amber" : "slate"}>{c.account?.tier}</Badge></td><td className="td">{c.account?.balance.toLocaleString()}</td><td className="td">{c.account?.lifetime_points.toLocaleString()}</td><td className="td">{c.segment ? <Badge tone="brand">{c.segment}</Badge> : "—"}</td></tr>)}</tbody></table></div>}
    </>
  );
}
