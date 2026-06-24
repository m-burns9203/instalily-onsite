import type { ScoreBand } from "./types";

export const bandStyles: Record<ScoreBand, { label: string; chip: string; ring: string; text: string }> = {
  hot: {
    label: "Hot",
    chip: "bg-rose-100 text-rose-700 border-rose-200",
    ring: "ring-rose-400",
    text: "text-rose-600",
  },
  warm: {
    label: "Warm",
    chip: "bg-amber-100 text-amber-700 border-amber-200",
    ring: "ring-amber-400",
    text: "text-amber-600",
  },
  nurture: {
    label: "Nurture",
    chip: "bg-sky-100 text-sky-700 border-sky-200",
    ring: "ring-sky-400",
    text: "text-sky-600",
  },
  unscored: {
    label: "Unscored",
    chip: "bg-slate-100 text-slate-600 border-slate-200",
    ring: "ring-slate-300",
    text: "text-slate-500",
  },
};

export const certStyles: Record<string, string> = {
  "Master Elite": "bg-brand-600 text-white",
  "President's Club": "bg-indigo-600 text-white",
  Certified: "bg-brand-100 text-brand-700",
};

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function scoreColor(score: number | null): string {
  if (score == null) return "#94a3b8";
  if (score >= 80) return "#e11d48";
  if (score >= 60) return "#d97706";
  return "#0284c7";
}
