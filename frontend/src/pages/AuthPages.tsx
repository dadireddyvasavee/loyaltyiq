import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorBox } from "../components/ui";
import { useAuth } from "../lib/auth";

type Field = { name: string; label: string; type?: string };

function AuthForm({ title, fields, submit, footer, brand }: { title: string; fields: Field[]; brand: string;
  submit: (v: Record<string, string>) => Promise<void>; footer: JSX.Element }) {
  const [v, setV] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const onSubmit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await submit(v); nav("/app"); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={onSubmit} className="card w-full max-w-sm space-y-4">
        <Link to="/" className="text-lg font-bold text-brand-600">{brand}</Link>
        <h1 className="text-xl font-semibold">{title}</h1>
        {err && <ErrorBox msg={err} />}
        {fields.map((f) => (
          <label key={f.name} className="block"><span className="label">{f.label}</span>
            <input className="input" required type={f.type ?? "text"} value={v[f.name] ?? ""}
              onChange={(e) => setV({ ...v, [f.name]: e.target.value })} /></label>))}
        <button className="btn w-full" disabled={busy}>{busy ? "Please wait…" : title}</button>
        <p className="text-center text-sm text-slate-500">{footer}</p>
      </form>
    </div>
  );
}

export function Login({ brand }: { brand: string }) {
  const { login } = useAuth();
  return <AuthForm brand={brand} title="Sign in" fields={[{ name: "email", label: "Email", type: "email" }, { name: "password", label: "Password", type: "password" }]}
    submit={(v) => login(v.email, v.password)} footer={<>No account? <Link className="text-brand-600" to="/register">Create one</Link></>} />;
}

export function Register({ brand, extra = [] }: { brand: string; extra?: Field[] }) {
  const { register } = useAuth();
  return <AuthForm brand={brand} title="Create account"
    fields={[...extra, { name: "full_name", label: "Full name" }, { name: "email", label: "Email", type: "email" },
      { name: "password", label: "Password (min 8 chars)", type: "password" }]}
    submit={register} footer={<>Have an account? <Link className="text-brand-600" to="/login">Sign in</Link></>} />;
}
