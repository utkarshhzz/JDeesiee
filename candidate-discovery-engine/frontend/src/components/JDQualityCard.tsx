import { motion } from 'framer-motion';
import { FileCheck, AlertTriangle, Lightbulb, CheckCircle } from 'lucide-react';
import type { JDQualityScore } from '../types';

interface JDQualityCardProps {
  quality: JDQualityScore;
}

function ScoreBar({ label, value, max = 10 }: { label: string; value: number; max?: number }) {
  const pct = (value / max) * 100;
  const color =
    value >= 8 ? 'var(--accent-emerald)' :
    value >= 5 ? 'var(--accent-amber)' :
    'var(--accent-red)';

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
          {label}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color }}>{value}/10</span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 3,
          background: 'rgba(255,255,255,0.06)',
          overflow: 'hidden',
        }}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          style={{
            height: '100%',
            borderRadius: 3,
            background: color,
          }}
        />
      </div>
    </div>
  );
}

export default function JDQualityCard({ quality }: JDQualityCardProps) {
  const overallColor =
    quality.overall >= 8 ? 'var(--accent-emerald)' :
    quality.overall >= 5 ? 'var(--accent-amber)' :
    'var(--accent-red)';

  const overallIcon =
    quality.overall >= 8 ? <CheckCircle size={16} style={{ color: overallColor }} /> :
    quality.overall >= 5 ? <AlertTriangle size={16} style={{ color: overallColor }} /> :
    <AlertTriangle size={16} style={{ color: overallColor }} />;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card"
      style={{ padding: 20, marginBottom: 12 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <FileCheck size={16} style={{ color: 'var(--accent-indigo-light)' }} />
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--text-secondary)',
            letterSpacing: '0.05em',
          }}
        >
          JD QUALITY
        </span>
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
          {overallIcon}
          <span style={{ fontSize: 14, fontWeight: 800, color: overallColor }}>
            {quality.overall}/10
          </span>
        </span>
      </div>

      <ScoreBar label="Clarity" value={quality.clarity} />
      <ScoreBar label="Specificity" value={quality.specificity} />
      <ScoreBar label="Inclusivity" value={quality.inclusivity} />

      {quality.suggestions.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Lightbulb size={13} style={{ color: 'var(--accent-amber)' }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
              SUGGESTIONS
            </span>
          </div>
          {quality.suggestions.map((s, i) => (
            <p
              key={i}
              style={{
                fontSize: 12,
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
                marginBottom: 4,
                paddingLeft: 12,
                borderLeft: '2px solid var(--border-color)',
              }}
            >
              {s}
            </p>
          ))}
        </div>
      )}
    </motion.div>
  );
}
