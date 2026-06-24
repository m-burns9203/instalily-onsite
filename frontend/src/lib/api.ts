import type {
  Health,
  LeadDetail,
  LeadListResponse,
  Stats,
} from "./types";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export interface LeadQuery {
  search?: string;
  certification?: string;
  min_score?: number;
  sort?: string;
}

export const api = {
  health: () => http<Health>("/api/health"),
  stats: () => http<Stats>("/api/stats"),
  leads: (q: LeadQuery = {}) => {
    const params = new URLSearchParams();
    if (q.search) params.set("search", q.search);
    if (q.certification) params.set("certification", q.certification);
    if (q.min_score != null) params.set("min_score", String(q.min_score));
    if (q.sort) params.set("sort", q.sort);
    params.set("limit", "200");
    return http<LeadListResponse>(`/api/leads?${params.toString()}`);
  },
  lead: (id: number) => http<LeadDetail>(`/api/leads/${id}`),
  runPipeline: (reenrich = false) =>
    http<{ mock_mode: boolean }>("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reenrich }),
    }),
};
