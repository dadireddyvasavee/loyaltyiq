import { Link } from "react-router-dom";

const f = [["Points engine", "Configurable earn rules, tiers, FIFO expiry, idempotent purchases and race-safe redemptions."],
  ["Smart segments", "RFM scoring + K-means clustering with plain-English rules for every segment."],
  ["Reward recommendations", "Per-customer reward ranking from spend, preferences, segment and redemption history, with reasons."],
  ["AI campaigns, human-approved", "Generate ideas and personalised messages with an LLM; nothing goes out until a manager approves it."]];

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 to-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between p-6"><span className="text-xl font-bold text-brand-600">LoyaltyIQ</span>
        <div className="flex gap-2"><Link to="/login" className="btn-ghost">Sign in</Link><Link to="/register" className="btn">Start free</Link></div></header>
      <section className="mx-auto max-w-4xl px-6 py-16 text-center">
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Know your customers. Reward them right.</h1>
        <p className="mt-5 text-lg text-slate-600">A loyalty platform that segments your customers, recommends the reward each one will value, and drafts targeted campaigns you approve.</p>
        <Link to="/register" className="btn mt-8 px-6 py-3 text-base">Create your program</Link>
        <p className="mt-3 text-xs text-slate-500">Want to explore first? If the server was started with synthetic data, sign in as demo@loyaltyiq.demo / demo12345 (all data is labelled SYNTHETIC).</p>
      </section>
      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-20 md:grid-cols-4">{f.map(([t, d]) => <div key={t} className="card"><h3 className="font-semibold">{t}</h3><p className="mt-2 text-sm text-slate-600">{d}</p></div>)}</section>
    </div>
  );
}
