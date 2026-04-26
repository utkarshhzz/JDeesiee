import { Zap, Database, Cpu, Clock, CheckCircle } from 'lucide-react';
import type { LatencyBreakdown } from '../types';

interface LatencyBarProps {
  latency: LatencyBreakdown;
  candidatesSearched: number;
}

export default function LatencyBar({ latency, candidatesSearched }: LatencyBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '12px 20px',
        background: 'var(--bg-card)',
        borderRadius: 12,
        border: '1px solid var(--border-color)',
        flexWrap: 'wrap',
      }}
    >
      <Zap size={14} style={{ color: 'var(--accent-indigo-light)' }} />
      <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
        PERFORMANCE
      </span>

      <span style={{ color: 'var(--border-color)', margin: '0 4px' }}>|</span>

      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
        <Database size={12} style={{ color: 'var(--accent-cyan)' }} />
        <span style={{ color: 'var(--text-secondary)' }}>
          Stage 1: <strong style={{ color: 'var(--text-primary)' }}>{latency.stage1_ms}ms</strong>
        </span>
      </span>

      <span style={{ color: 'var(--border-color)', margin: '0 4px' }}>|</span>

      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
        <Cpu size={12} style={{ color: 'var(--accent-amber)' }} />
        <span style={{ color: 'var(--text-secondary)' }}>
          Stage 2: <strong style={{ color: 'var(--text-primary)' }}>{latency.stage2_ms}ms</strong>
        </span>
      </span>

      <span style={{ color: 'var(--border-color)', margin: '0 4px' }}>|</span>

      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
        <Clock size={12} style={{ color: 'var(--accent-emerald)' }} />
        <span style={{ color: 'var(--text-secondary)' }}>
          Total: <strong style={{ color: 'var(--accent-emerald)' }}>{latency.total_ms}ms</strong>
        </span>
      </span>

      <span style={{ color: 'var(--border-color)', margin: '0 4px' }}>|</span>

      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        <strong style={{ color: 'var(--text-primary)' }}>
          {candidatesSearched.toLocaleString()}
        </strong>{' '}
        candidates searched
      </span>

      {latency.embedding_cached && (
        <>
          <span style={{ color: 'var(--border-color)', margin: '0 4px' }}>|</span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              color: 'var(--accent-emerald)',
              fontWeight: 600,
            }}
          >
            <CheckCircle size={12} />
            Cache Hit
          </span>
        </>
      )}
    </div>
  );
}
