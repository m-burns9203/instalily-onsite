import type { ScoreBand } from "../lib/types";
import { bandStyles, certStyles, scoreColor } from "../lib/ui";

export function ScoreRing({ score }: { score: number | null }) {
  const value = score ?? 0;
  const color = scoreColor(score);
  const circumference = 2 * Math.PI * 18;
  const offset = circumference * (1 - value / 100);
  return (
    <div className="relative h-12 w-12 shrink-0">
      <svg viewBox="0 0 44 44" className="h-12 w-12 -rotate-90">
        <circle cx="22" cy="22" r="18" fill="none" stroke="#e2e8f0" strokeWidth="4" />
        <circle
          cx="22"
          cy="22"
          r="18"
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center text-sm font-bold"
        style={{ color }}
      >
        {score ?? "—"}
      </span>
    </div>
  );
}

export function BandChip({ band }: { band: ScoreBand }) {
  const s = bandStyles[band];
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${s.chip}`}>
      {s.label}
    </span>
  );
}

export function CertBadge({ certification }: { certification: string | null }) {
  if (!certification) {
    return (
      <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
        Uncertified
      </span>
    );
  }
  const cls = certStyles[certification] ?? "bg-slate-200 text-slate-700";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ${cls}`}>
      {certification === "Master Elite" && <span aria-hidden>★</span>}
      {certification}
    </span>
  );
}

export function Stars({ rating, reviews }: { rating: number | null; reviews: number | null }) {
  if (rating == null) return null;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-500">
      <span className="text-amber-500">★</span>
      <span className="font-medium text-slate-700">{rating.toFixed(1)}</span>
      {reviews != null && <span>({reviews})</span>}
    </span>
  );
}
