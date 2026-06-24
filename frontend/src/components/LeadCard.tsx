import { Link } from "react-router-dom";
import type { LeadSummary } from "../lib/types";
import { initials } from "../lib/ui";
import { BandChip, CertBadge, ScoreRing, Stars } from "./Badges";

export function LeadCard({ lead }: { lead: LeadSummary }) {
  return (
    <Link
      to={`/leads/${lead.id}`}
      className="group block rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white">
          {initials(lead.name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="truncate font-semibold text-slate-900 group-hover:text-brand-700">
              {lead.name}
            </h3>
            <BandChip band={lead.score_band} />
          </div>
          <p className="mt-0.5 text-sm text-slate-500">
            {[lead.city, lead.state].filter(Boolean).join(", ")}
            {lead.distance_miles != null && (
              <span className="text-slate-400"> · {lead.distance_miles.toFixed(1)} mi</span>
            )}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <CertBadge certification={lead.certification} />
            <Stars rating={lead.rating} reviews={lead.review_count} />
          </div>
        </div>
        <ScoreRing score={lead.lead_score} />
      </div>

      {lead.summary && (
        <p className="mt-4 line-clamp-2 text-sm leading-relaxed text-slate-600">
          {lead.summary}
        </p>
      )}

      {lead.top_signal && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <span aria-hidden className="mt-px">⚡</span>
          <span className="font-medium">{lead.top_signal}</span>
        </div>
      )}
    </Link>
  );
}
