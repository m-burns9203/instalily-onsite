export type ScoreBand = "hot" | "warm" | "nurture" | "unscored";

export interface LeadSummary {
  id: number;
  name: string;
  certification: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  distance_miles: number | null;
  rating: number | null;
  review_count: number | null;
  phone: string | null;
  website: string | null;
  lead_score: number | null;
  score_band: ScoreBand;
  enrichment_status: string;
  summary: string | null;
  top_signal: string | null;
}

export interface RecommendedProduct {
  product: string;
  reason: string;
}

export interface DecisionMaker {
  name: string | null;
  title: string | null;
  rationale: string | null;
  linkedin_url: string | null;
}

export interface Enrichment {
  summary: string | null;
  estimated_size: string | null;
  years_in_business: string | null;
  specialties: string[];
  service_areas: string[];
  recent_activity: string | null;
  recommended_products: RecommendedProduct[];
  talking_points: string[];
  buying_signals: string[];
  outreach_strategy: string | null;
  sources: string[];
  model_version: string | null;
}

export interface LeadDetail extends LeadSummary {
  source: string | null;
  source_url: string | null;
  address: string | null;
  enrichment: Enrichment | null;
  decision_makers: DecisionMaker[];
}

export interface LeadListResponse {
  total: number;
  items: LeadSummary[];
}

export interface Stats {
  total_leads: number;
  enriched: number;
  pending: number;
  hot_leads: number;
  avg_score: number | null;
  by_certification: Record<string, number>;
}

export interface Health {
  status: string;
  mock_mode: boolean;
  target_zip: string;
  radius_miles: number;
}
