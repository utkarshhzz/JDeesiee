import axios from 'axios';
import type {
  SearchRequest,
  SearchResponse,
  CandidateDetailResponse,
  SearchHistoryResponse,
} from '../types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

/* ── Search (text-based) ──────────────────────────────────────── */
export async function searchCandidates(
  request: SearchRequest
): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>('/search', request);
  return data;
}

/* ── Search (file upload) ─────────────────────────────────────── */
export async function uploadAndSearch(
  file: File,
  topK: number = 20,
  onProgress?: (pct: number) => void
): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('top_k', String(topK));

  const { data } = await api.post<SearchResponse>('/ingest', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total && onProgress) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });
  return data;
}

/* ── Candidate Detail ─────────────────────────────────────────── */
export async function getCandidateDetail(
  candidateId: string
): Promise<CandidateDetailResponse> {
  const { data } = await api.get<CandidateDetailResponse>(
    `/candidates/${candidateId}`
  );
  return data;
}

/* ── Search History ───────────────────────────────────────────── */
export async function getSearchHistory(
  limit: number = 20
): Promise<SearchHistoryResponse> {
  const { data } = await api.get<SearchHistoryResponse>('/search/history', {
    params: { limit },
  });
  return data;
}

export default api;
