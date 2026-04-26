import { useState } from 'react';
import { Search as SearchIcon, Loader2, SlidersHorizontal, X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import JDUploader from '../components/JDUploader';
import SearchResults from '../components/SearchResults';
import SearchHistorySidebar from '../components/SearchHistorySidebar';
import { useSearch, useFileSearch } from '../hooks/useSearch';
import type { SearchResponse } from '../types';

export default function SearchPage() {
  const [jdText, setJdText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showHistory, setShowHistory] = useState(true);
  const [topK, setTopK] = useState(20);
  const [locationCountry, setLocationCountry] = useState('');
  const [minYears, setMinYears] = useState('');

  const textSearch = useSearch();
  const fileSearch = useFileSearch();
  const queryClient = useQueryClient();

  const isLoading = textSearch.isPending || fileSearch.isPending;
  const searchData: SearchResponse | null =
    textSearch.data ?? fileSearch.data ?? null;
  const error = textSearch.error ?? fileSearch.error;

  const canSearch =
    !isLoading && (jdText.length >= 50 || selectedFile !== null);

  function handleSearch() {
    if (selectedFile) {
      fileSearch.mutate(
        { file: selectedFile, topK },
        {
          onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['search-history'] });
          },
        }
      );
    } else if (jdText.length >= 50) {
      const filters: Record<string, unknown> = {};
      if (locationCountry) filters.location_country = locationCountry;
      if (minYears) filters.min_years = parseInt(minYears, 10);

      textSearch.mutate(
        {
          jd_text: jdText,
          filters: Object.keys(filters).length > 0 ? filters as any : undefined,
          top_k: topK,
        },
        {
          onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['search-history'] });
          },
        }
      );
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        background: 'var(--bg-primary)',
      }}
    >
      {/* ── History Sidebar ──────────────────────────────────────── */}
      {showHistory && (
        <aside
          style={{
            width: 300,
            borderRight: '1px solid var(--border-color)',
            background: 'var(--bg-secondary)',
            overflowY: 'auto',
            flexShrink: 0,
          }}
        >
          <SearchHistorySidebar
            onSelectJd={(text) => {
              setJdText(text);
              setSelectedFile(null);
            }}
          />
        </aside>
      )}

      {/* ── Main Content ─────────────────────────────────────────── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <header
          style={{
            padding: '20px 32px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-secondary)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background: 'var(--gradient-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <SearchIcon size={20} color="white" />
            </div>
            <div>
              <h1 style={{ fontSize: 20, fontWeight: 800 }}>
                <span className="gradient-text">Candidate Discovery</span>
              </h1>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                AI-powered talent matching engine
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn-secondary"
              onClick={() => setShowHistory(!showHistory)}
              style={{ fontSize: 12 }}
            >
              {showHistory ? 'Hide' : 'Show'} History
            </button>
          </div>
        </header>

        {/* Content area */}
        <div
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: '380px 1fr',
            gap: 0,
            overflow: 'hidden',
          }}
        >
          {/* ── Left Panel: JD Input ─────────────────────────────── */}
          <div
            style={{
              padding: 24,
              borderRight: '1px solid var(--border-color)',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <h2
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--text-secondary)',
                letterSpacing: '0.05em',
              }}
            >
              JOB DESCRIPTION
            </h2>

            <JDUploader
              jdText={jdText}
              onJdTextChange={setJdText}
              onFileSelect={(file) => setSelectedFile(file)}
              selectedFile={selectedFile}
              onClearFile={() => setSelectedFile(null)}
              isLoading={isLoading}
            />

            {/* Filters toggle */}
            <button
              className="btn-secondary"
              onClick={() => setShowFilters(!showFilters)}
              style={{ width: '100%' }}
            >
              <SlidersHorizontal size={14} />
              {showFilters ? 'Hide Filters' : 'Show Filters'}
            </button>

            {/* Filters */}
            {showFilters && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                  padding: 16,
                  background: 'var(--bg-card)',
                  borderRadius: 12,
                  border: '1px solid var(--border-color)',
                }}
              >
                <div>
                  <label
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--text-muted)',
                      marginBottom: 6,
                      display: 'block',
                    }}
                  >
                    Country
                  </label>
                  <input
                    className="input-field"
                    placeholder="e.g. India, USA"
                    value={locationCountry}
                    onChange={(e) => setLocationCountry(e.target.value)}
                    disabled={isLoading}
                  />
                </div>
                <div>
                  <label
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--text-muted)',
                      marginBottom: 6,
                      display: 'block',
                    }}
                  >
                    Min. Experience (years)
                  </label>
                  <input
                    className="input-field"
                    type="number"
                    min="0"
                    max="40"
                    placeholder="e.g. 5"
                    value={minYears}
                    onChange={(e) => setMinYears(e.target.value)}
                    disabled={isLoading}
                  />
                </div>
                <div>
                  <label
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--text-muted)',
                      marginBottom: 6,
                      display: 'block',
                    }}
                  >
                    Results (top K)
                  </label>
                  <input
                    className="input-field"
                    type="number"
                    min="1"
                    max="50"
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    disabled={isLoading}
                  />
                </div>
              </div>
            )}

            {/* Search button */}
            <button
              className="btn-primary"
              onClick={handleSearch}
              disabled={!canSearch}
              style={{ width: '100%', padding: '14px 28px', fontSize: 15 }}
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
                  Searching...
                </>
              ) : (
                <>
                  <SearchIcon size={18} />
                  Find Candidates
                </>
              )}
            </button>

            {/* Char count hint */}
            {!selectedFile && jdText.length > 0 && jdText.length < 50 && (
              <p style={{ fontSize: 12, color: 'var(--accent-amber)' }}>
                {50 - jdText.length} more characters needed
              </p>
            )}

            {/* Error */}
            {error && (
              <div
                style={{
                  padding: '12px 16px',
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: 10,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <X size={14} style={{ color: 'var(--accent-red)' }} />
                <span style={{ fontSize: 13, color: 'var(--accent-red)' }}>
                  {error.message || 'Search failed. Please try again.'}
                </span>
              </div>
            )}
          </div>

          {/* ── Right Panel: Results ─────────────────────────────── */}
          <div style={{ padding: 24, overflowY: 'auto' }}>
            <SearchResults data={searchData} isLoading={isLoading} />
          </div>
        </div>
      </main>

      {/* Spinner keyframe (inline since Tailwind v4 doesn't ship animate-spin by default) */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
