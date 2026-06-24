import { useEffect, useMemo, useState } from "react";
import { api, type LeadQuery } from "../lib/api";
import type { Health, LeadSummary, Stats } from "../lib/types";
import { LeadCard } from "../components/LeadCard";

const SORTS = [
  { key: "score", label: "Lead score" },
  { key: "rating", label: "Rating" },
  { key: "distance", label: "Distance" },
  { key: "name", label: "Name" },
];

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent ?? "text-slate-900"}`}>{value}</div>
    </div>
  );
}

export function Dashboard() {
  const [leads, setLeads] = useState<LeadSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [cert, setCert] = useState("");
  const [hotOnly, setHotOnly] = useState(false);
  const [sort, setSort] = useState("score");

  const query: LeadQuery = useMemo(
    () => ({
      search: search || undefined,
      certification: cert || undefined,
      min_score: hotOnly ? 80 : undefined,
      sort,
    }),
    [search, cert, hotOnly, sort]
  );

  async function loadLeads() {
    try {
      const res = await api.leads(query);
      setLeads(res.items);
      setTotal(res.total);
      setError(null);
    } catch (e) {
      setError(`Couldn't load leads (${String(e)})`);
    }
  }

  async function loadAll() {
    try {
      const [s, h] = await Promise.all([api.stats(), api.health()]);
      setStats(s);
      setHealth(h);
      await loadLeads();
    } catch (e) {
      setError(
        `Couldn't reach the API — is the backend running on :8000? (${String(e)})`
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      loadLeads();
    }, 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  async function refreshLeads() {
    setRunning(true);
    try {
      // Note the run we're replacing so we can detect the *new* run finishing.
      const before = await api.runsLatest().catch(() => null);
      await api.runPipeline(false);
      // Poll the run status, refreshing as it fills in, until the new run
      // completes (or we hit a safety cap).
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        await Promise.all([api.stats().then(setStats), loadLeads()]);
        const run = await api.runsLatest().catch(() => null);
        if (run && run.run_id !== before?.run_id && run.finished_at) break;
      }
    } catch (e) {
      setError(`Pipeline run failed (${String(e)})`);
    } finally {
      setRunning(false);
    }
  }

  const certs = stats ? Object.keys(stats.by_certification).filter((c) => c !== "None") : [];

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <span className="text-brand-600">⛵</span> Cosailor Insights
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            AI-generated roofing-contractor leads for distributor account planning ·
            ZIP {health?.target_zip ?? "10013"} · {health?.radius_miles ?? 25} mi radius
          </p>
        </div>
        <div className="flex items-center gap-3">
          {health?.mock_mode && (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700">
              Demo data (mock mode)
            </span>
          )}
          <button
            onClick={refreshLeads}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-60"
          >
            {running ? "Refreshing…" : "↻ Run pipeline"}
          </button>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <span aria-hidden>⚠</span>
          <span>{error}</span>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total leads" value={String(stats.total_leads)} />
          <StatCard label="Hot leads" value={String(stats.hot_leads)} accent="text-rose-600" />
          <StatCard label="Avg score" value={stats.avg_score?.toFixed(0) ?? "—"} accent="text-brand-600" />
          <StatCard label="Enriched" value={`${stats.enriched}/${stats.total_leads}`} accent="text-emerald-600" />
        </div>
      )}

      {/* Filters */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search contractors…"
          className="w-full max-w-xs rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
        />
        <select
          value={cert}
          onChange={(e) => setCert(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none"
        >
          <option value="">All certifications</option>
          {certs.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none"
        >
          {SORTS.map((s) => (
            <option key={s.key} value={s.key}>Sort: {s.label}</option>
          ))}
        </select>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
          <input type="checkbox" checked={hotOnly} onChange={(e) => setHotOnly(e.target.checked)} />
          Hot only
        </label>
        <span className="ml-auto text-sm text-slate-400">{total} result{total === 1 ? "" : "s"}</span>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="mt-16 text-center text-slate-400">Loading leads…</div>
      ) : leads.length === 0 ? (
        <div className="mt-16 text-center text-slate-400">No leads match your filters.</div>
      ) : (
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          {leads.map((lead) => (
            <LeadCard key={lead.id} lead={lead} />
          ))}
        </div>
      )}
    </div>
  );
}
