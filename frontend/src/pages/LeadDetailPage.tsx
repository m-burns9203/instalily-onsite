import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { LeadDetail } from "../lib/types";
import { BandChip, CertBadge, ScoreRing, Stars } from "../components/Badges";
import { OutreachPanel } from "../components/OutreachPanel";

function Section({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        <span aria-hidden>{icon}</span> {title}
      </h2>
      {children}
    </section>
  );
}

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
      {children}
    </span>
  );
}

export function LeadDetailPage() {
  const { id } = useParams();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.lead(Number(id)).then(setLead).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="mx-auto max-w-4xl px-6 py-10 text-rose-600">{error}</div>;
  if (!lead) return <div className="mx-auto max-w-4xl px-6 py-10 text-slate-400">Loading…</div>;

  const e = lead.enrichment;

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <Link to="/" className="text-sm text-brand-600 hover:underline">← Back to leads</Link>

      {/* Hero */}
      <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{lead.name}</h1>
              <BandChip band={lead.score_band} />
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {[lead.address, lead.city, lead.state, lead.zip_code].filter(Boolean).join(", ")}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <CertBadge certification={lead.certification} />
              <Stars rating={lead.rating} reviews={lead.review_count} />
              {lead.distance_miles != null && (
                <span className="text-xs text-slate-500">{lead.distance_miles.toFixed(1)} mi away</span>
              )}
              {e?.estimated_size && <Pill>{e.estimated_size}</Pill>}
              {e?.years_in_business && <Pill>{e.years_in_business}</Pill>}
            </div>
            <div className="mt-3 flex flex-wrap gap-4 text-sm">
              {lead.phone && <a href={`tel:${lead.phone}`} className="text-brand-600 hover:underline">📞 {lead.phone}</a>}
              {lead.website && (
                <a href={lead.website} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                  🌐 Website
                </a>
              )}
              {lead.source_url && (
                <a href={lead.source_url} target="_blank" rel="noreferrer" className="text-slate-400 hover:underline">
                  GAF profile ↗
                </a>
              )}
            </div>
          </div>
          <div className="flex flex-col items-center">
            <div className="scale-150">
              <ScoreRing score={lead.lead_score} />
            </div>
            <span className="mt-3 text-xs font-medium uppercase tracking-wide text-slate-400">Lead score</span>
            {lead.score_breakdown.length > 0 && (
              <div className="mt-4 w-48 space-y-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                  Why this score
                </div>
                {lead.score_breakdown.map((c) => (
                  <div key={c.label} title={c.detail ?? undefined}>
                    <div className="flex items-baseline justify-between gap-2 text-[11px] text-slate-500">
                      <span className="truncate">{c.label}</span>
                      <span className="font-semibold text-slate-700">
                        +{c.points}
                        <span className="font-normal text-slate-300">/{c.max}</span>
                      </span>
                    </div>
                    <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-brand-500"
                        style={{ width: `${Math.min(100, (c.points / c.max) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        {e?.summary && <p className="mt-5 leading-relaxed text-slate-700">{e.summary}</p>}
      </div>

      {/* One-click, ready-to-send outreach draft */}
      <OutreachPanel leadId={lead.id} />

      {!e ? (
        <p className="mt-6 text-slate-400">This lead has not been enriched yet.</p>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
          {e.buying_signals.length > 0 && (
            <Section title="Why now — buying signals" icon="⚡">
              <ul className="space-y-2">
                {e.buying_signals.map((s, i) => (
                  <li key={i} className="flex gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                    <span aria-hidden>✓</span> {s}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {e.recommended_products.length > 0 && (
            <Section title="Recommended products to pitch" icon="📦">
              <ul className="space-y-3">
                {e.recommended_products.map((p, i) => (
                  <li key={i}>
                    <div className="font-semibold text-slate-800">{p.product}</div>
                    <div className="text-sm text-slate-500">{p.reason}</div>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {e.talking_points.length > 0 && (
            <Section title="Talking points" icon="💬">
              <ul className="space-y-2">
                {e.talking_points.map((t, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-brand-500">•</span> {t}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title="Outreach strategy" icon="🎯">
            <p className="text-sm leading-relaxed text-slate-700">{e.outreach_strategy}</p>
            {lead.decision_makers.length > 0 && (
              <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
                {lead.decision_makers.map((dm, i) => (
                  <div key={i}>
                    <div className="text-sm font-semibold text-slate-800">
                      {dm.title}
                      {dm.name && dm.name !== "Unknown" && <span className="text-slate-500"> — {dm.name}</span>}
                    </div>
                    {dm.rationale && <div className="text-xs text-slate-500">{dm.rationale}</div>}
                  </div>
                ))}
              </div>
            )}
          </Section>

          {(e.specialties.length > 0 || e.service_areas.length > 0) && (
            <Section title="Profile" icon="🏗️">
              {e.specialties.length > 0 && (
                <div className="mb-3">
                  <div className="mb-1 text-xs font-medium text-slate-400">Specialties</div>
                  <div className="flex flex-wrap gap-1.5">
                    {e.specialties.map((s, i) => <Pill key={i}>{s}</Pill>)}
                  </div>
                </div>
              )}
              {e.service_areas.length > 0 && (
                <div>
                  <div className="mb-1 text-xs font-medium text-slate-400">Service areas</div>
                  <div className="flex flex-wrap gap-1.5">
                    {e.service_areas.filter(Boolean).map((s, i) => <Pill key={i}>{s}</Pill>)}
                  </div>
                </div>
              )}
              {e.recent_activity && (
                <p className="mt-3 text-sm text-slate-600">
                  <span className="font-medium text-slate-700">Recent: </span>
                  {e.recent_activity}
                </p>
              )}
            </Section>
          )}

          {e.sources.length > 0 && (
            <Section title="Sources" icon="🔗">
              <ul className="space-y-1">
                {e.sources.map((s, i) => (
                  <li key={i} className="truncate text-sm">
                    <a href={s} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                      {s}
                    </a>
                  </li>
                ))}
              </ul>
              {e.model_version && (
                <p className="mt-3 text-xs text-slate-400">Generated by {e.model_version}</p>
              )}
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
