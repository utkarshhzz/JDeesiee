import { useMutation } from '@tanstack/react-query';
import { searchCandidates, uploadAndSearch } from '../api/client';
import type { SearchRequest, SearchResponse } from '../types';

export function useSearch() {
  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: searchCandidates,
  });
}

export function useFileSearch() {
  return useMutation<
    SearchResponse,
    Error,
    { file: File; topK?: number }
  >({
    mutationFn: ({ file, topK }) => uploadAndSearch(file, topK),
  });
}
