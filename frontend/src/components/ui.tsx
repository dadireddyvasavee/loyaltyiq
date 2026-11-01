import { ReactNode } from "react";
import { Navigate, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";

export const Spinner = () => (
  <div className="flex justify-center p-8" role="status" aria-label="loading">
    <div className="h-6 w-6 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
  </div>
);
export const ErrorBox = ({ msg }: { msg: string }) => (
  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">{msg}</div>
);
export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center">
    <p className="font-medium text-slate-700">{title}</p>{hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
  </div>
);
export const Stat = ({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) => (
  <div className="card"><p className="label">{label}</p><p className="text-2xl font-semibold text-slate-900">{value}</p>
    {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}</div>
);
export const PageHeader = ({ title, children }: { title: string; children?: ReactNode }) => (
  <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
    <h1 className="text-2xl font-semibold text-slate-900">{title}</h1><div className="flex gap-2">{children}</div>
  </div>
);
export const Badge = ({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "green" | "red" | "amber" | "brand" }) => {
  const c = { slate: "bg-slate-100 text-slate-700", green: "bg-emerald-100 text-emerald-700", red: "bg-red-100 text-red-700",
    amber: "bg-amber-100 text-amber-700", brand: "bg-brand-100 text-brand-700" }[tone];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${c}`}>{children}</span>;
};

export function RequireAuth() {
  const { user, ready } = useAuth();
  if (!ready) return <Spinner />;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

export function AppShell({ brand, nav }: { brand: string; nav: { to: string; label: string }[] }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-slate-200 bg-white md:w-60 md:border-b-0 md:border-r">
        <div className="px-5 py-4 text-lg font-bold text-brand-600">{brand}</div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end className={({ isActive }) =>
              `whitespace-nowrap rounded-lg px-3 py-2 text-sm ${isActive ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-100"}`}>
              {n.label}
            </NavLink>))}
        </nav>
        <div className="hidden border-t border-slate-200 p-4 text-sm md:block">
          <p className="truncate font-medium text-slate-800">{user?.full_name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button className="mt-2 text-xs text-red-600 hover:underline" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-8"><Outlet /></main>
    </div>
  );
}
