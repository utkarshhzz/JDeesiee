import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { Users, SearchX } from 'lucide-react';
import CandidateCard from './CandidateCard';
import LatencyBar from './LatencyBar';
import type { SearchResponse } from '../types';

interface SearchResultsProps {
  data: SearchResponse | null;
  isLoading: boolean;
}

function SkeletonCard({ index }: { index: number }) {
  return (
    <div
      className="glass-card"
      style={{
        padding: 24,
        animationDelay: `${index * 0.1}s`,
      }}
    >
      <div style={{ display: 'flex', gap: 20 }}>
        <div className="skeleton" style={{ width: 36, height: 36, borderRadius: 10 }} />
        <div style={{ flex: 1 }}>
          <div className="skeleton" style={{ width: '40%', height: 20, marginBottom: 10 }} />
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <div className="skeleton" style={{ width: 80, height: 18 }} />
            <div className="skeleton" style={{ width: 60, height: 18 }} />
            <div className="skeleton" style={{ width: 70, height: 18 }} />
          </div>
          <div className="skeleton" style={{ width: '90%', height: 14, marginBottom: 8 }} />
          <div className="skeleton" style={{ width: '70%', height: 14, marginBottom: 14 }} />
          <div style={{ display: 'flex', gap: 6 }}>
            <div className="skeleton" style={{ width: 60, height: 24, borderRadius: 8 }} />
            <div className="skeleton" style={{ width: 72, height: 24, borderRadius: 8 }} />
            <div className="skeleton" style={{ width: 56, height: 24, borderRadius: 8 }} />
          </div>
        </div>
        <div className="skeleton" style={{ width: 68, height: 68, borderRadius: '50%' }} />
      </div>
    </div>
  );
}

export default function SearchResults({ data, isLoading }: SearchResultsProps) {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 4,
          }}
        >
          <div
            className="skeleton"
            style={{ width: 14, height: 14, borderRadius: '50%' }}
          />
          <div className="skeleton" style={{ width: 180, height: 16 }} />
        </div>
        {[0, 1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} index={i} />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '80px 20px',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 80,
            height: 80,
            borderRadius: 20,
            background: 'rgba(99,102,241,0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 20,
          }}
        >
          <Users size={36} style={{ color: 'var(--accent-indigo)' }} />
        </div>
        <h3
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--text-primary)',
            marginBottom: 8,
          }}
        >
          Ready to discover talent
        </h3>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', maxWidth: 340 }}>
          Paste a job description or upload a file to find the best matching
          candidates from our database.
        </p>
      </div>
    );
  }

  if (data.candidates.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '80px 20px',
          textAlign: 'center',
        }}
      >
        <SearchX size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
          No matches found
        </h3>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', maxWidth: 340 }}>
          Try adjusting your job description or removing filters to broaden the search.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 4,
        }}
      >
        <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>
            {data.candidates.length}
          </strong>{' '}
          candidates matched
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Sorted by match score
        </span>
      </div>

      {/* Latency bar */}
      <LatencyBar
        latency={data.latency}
        candidatesSearched={data.total_candidates_searched}
      />

      {/* Cards */}
      <AnimatePresence>
        {data.candidates.map((candidate, index) => (
          <CandidateCard
            key={candidate.candidate_id}
            candidate={candidate}
            rank={index + 1}
            onClick={() => navigate(`/candidates/${candidate.candidate_id}`)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
