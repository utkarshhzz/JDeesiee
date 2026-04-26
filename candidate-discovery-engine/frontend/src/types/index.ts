/* ── Search API ──────────────────────────────────────────────── */

export interface SearchFilters {
  location_country?: string;
  location_city?: string;
  min_years?: number;
  education_level?: string;
}

export interface SearchRequest {
  jd_text: string;
  filters?: SearchFilters;
  top_k?: number;
}

export interface CandidateResponse {
  candidate_id: string;
  match_score: number;
  justifications: string[];
  matched_section: string;
  skills: string;
  location: string;
  years_of_experience: number;
  education_level: string;
}

export interface LatencyBreakdown {
  stage1_ms: number;
  stage2_ms: number;
  total_ms: number;
  embedding_cached: boolean;
}

/* ── JD Quality (Feature C) ─────────────────────────────────── */

export interface JDQualityScore {
  clarity: number;
  specificity: number;
  inclusivity: number;
  overall: number;
  suggestions: string[];
}

/* ── DEI Analytics (Feature B) ──────────────────────────────── */

export interface AnalyticsData {
  country_distribution: Record<string, number>;
  experience_bands: Record<string, number>;
  education_distribution: Record<string, number>;
  avg_match_score: number;
  score_distribution: Record<string, number>;
}

/* ── Search Response ────────────────────────────────────────── */

export interface SearchResponse {
  search_event_id: string;
  candidates: CandidateResponse[];
  total_candidates_searched: number;
  latency: LatencyBreakdown;
  jd_quality?: JDQualityScore | null;
  analytics?: AnalyticsData | null;
}

/* ── Candidate Detail ───────────────────────────────────────── */

export interface CandidateDetail {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  location_city: string | null;
  location_country: string | null;
  years_of_experience: number | null;
  current_title: string | null;
  current_company: string | null;
  education_level: string | null;
  skills: string[];
  resume_text: string | null;
  is_active: boolean;
}

export interface MatchHistoryItem {
  search_event_id: string;
  match_score: number;
  justification_1: string;
  justification_2: string;
  rank: number;
  searched_at: string;
}

export interface CandidateDetailResponse {
  candidate: CandidateDetail;
  match_history: MatchHistoryItem[];
}

/* ── Search History ─────────────────────────────────────────── */

export interface SearchHistoryItem {
  search_event_id: string;
  jd_snippet: string;
  candidates_searched: number | null;
  total_latency_ms: number | null;
  embedding_cached: boolean | null;
  searched_at: string;
}

export interface SearchHistoryResponse {
  history: SearchHistoryItem[];
}
