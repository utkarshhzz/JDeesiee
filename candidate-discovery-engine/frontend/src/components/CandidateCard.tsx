import { useState } from 'react';
import { motion } from 'framer-motion';
import { MapPin, Briefcase, GraduationCap, ChevronRight, Sparkles, TrendingUp } from 'lucide-react';
import ScoreGauge from './ScoreGauge';
import type { CandidateResponse } from '../types';

interface CandidateCardProps {
  candidate: CandidateResponse;
  rank: number;
  onClick: () => void;
}

export default function CandidateCard({ candidate, rank, onClick }: CandidateCardProps) {
  const [showAllSkills, setShowAllSkills] = useState(false);

  const skills = candidate.skills
    ? candidate.skills.split(',').map((s) => s.trim()).filter(Boolean)
    : [];
  const visibleSkills = showAllSkills ? skills : skills.slice(0, 5);
  const remainingCount = skills.length - 5;

  const justifications = candidate.justifications.filter(Boolean);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: rank * 0.06 }}
      className="glass-card"
      style={{ padding: '24px', cursor: 'pointer' }}
      onClick={onClick}
    >
      <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
        {/* Rank badge */}
        <div
          style={{
            minWidth: 36,
            height: 36,
            borderRadius: 10,
            background:
              rank <= 3
                ? 'var(--gradient-primary)'
                : 'rgba(255,255,255,0.05)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: 14,
            color: rank <= 3 ? 'white' : 'var(--text-muted)',
            flexShrink: 0,
          }}
        >
          #{rank}
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Top row: name + score */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 16,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <h3
                style={{
                  fontSize: 17,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  marginBottom: 6,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                Candidate {candidate.candidate_id.slice(0, 8)}...
              </h3>

              {/* Meta badges */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                  }}
                >
                  <MapPin size={13} />
                  {candidate.location || 'Unknown'}
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                  }}
                >
                  <Briefcase size={13} />
                  {candidate.years_of_experience} yrs
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                  }}
                >
                  <GraduationCap size={13} />
                  {candidate.education_level}
                </span>
                <span
                  className="chip"
                  style={{
                    fontSize: 11,
                    padding: '2px 8px',
                    background: 'rgba(6,182,212,0.1)',
                    color: 'var(--accent-cyan)',
                    border: '1px solid rgba(6,182,212,0.2)',
                  }}
                >
                  {candidate.matched_section}
                </span>
              </div>
            </div>

            <ScoreGauge score={candidate.match_score} size={68} />
          </div>

          {/* Justifications */}
          {justifications.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              {justifications.slice(0, 2).map((j, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    gap: 8,
                    alignItems: 'flex-start',
                    marginBottom: 6,
                  }}
                >
                  {i === 0 ? (
                    <Sparkles
                      size={14}
                      style={{ color: 'var(--accent-emerald)', marginTop: 2, flexShrink: 0 }}
                    />
                  ) : (
                    <TrendingUp
                      size={14}
                      style={{ color: 'var(--accent-amber)', marginTop: 2, flexShrink: 0 }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: 13,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.5,
                    }}
                  >
                    {j}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Skills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {visibleSkills.map((skill) => (
              <span key={skill} className="chip">
                {skill}
              </span>
            ))}
            {!showAllSkills && remainingCount > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowAllSkills(true);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--accent-indigo-light)',
                  fontSize: 12,
                  cursor: 'pointer',
                  fontWeight: 600,
                  padding: '4px 8px',
                }}
              >
                +{remainingCount} more
              </button>
            )}
          </div>
        </div>

        {/* Arrow */}
        <ChevronRight
          size={20}
          style={{
            color: 'var(--text-muted)',
            flexShrink: 0,
            marginTop: 8,
          }}
        />
      </div>
    </motion.div>
  );
}
