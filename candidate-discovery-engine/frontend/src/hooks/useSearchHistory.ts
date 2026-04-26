import { useQuery } from '@tanstack/react-query';
import { getSearchHistory } from '../api/client';

export function useSearchHistory() {
  return useQuery({
    queryKey: ['search-history'],
    queryFn: () => getSearchHistory(20),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}
