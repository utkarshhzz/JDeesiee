import { createContext, useContext, useState, type ReactNode } from 'react';
import type { SearchResponse } from '../types';

interface SearchContextValue {
  lastResults: SearchResponse | null;
  setLastResults: (data: SearchResponse | null) => void;
  lastJdText: string;
  setLastJdText: (text: string) => void;
}

const SearchContext = createContext<SearchContextValue | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [lastResults, setLastResults] = useState<SearchResponse | null>(null);
  const [lastJdText, setLastJdText] = useState('');

  return (
    <SearchContext.Provider
      value={{ lastResults, setLastResults, lastJdText, setLastJdText }}
    >
      {children}
    </SearchContext.Provider>
  );
}

export function useSearchContext() {
  const ctx = useContext(SearchContext);
  if (!ctx) throw new Error('useSearchContext must be used within SearchProvider');
  return ctx;
}
