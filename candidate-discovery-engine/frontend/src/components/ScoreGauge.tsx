import { useEffect, useState } from 'react';

interface ScoreGaugeProps {
  score: number;
  size?: number;
  strokeWidth?: number;
}

function getScoreColor(score: number): string {
  if (score >= 80) return '#10b981';
  if (score >= 60) return '#f59e0b';
  return '#ef4444';
}

function getScoreGlow(score: number): string {
  if (score >= 80) return 'rgba(16,185,129,0.3)';
  if (score >= 60) return 'rgba(245,158,11,0.3)';
  return 'rgba(239,68,68,0.3)';
}

export default function ScoreGauge({
  score,
  size = 72,
  strokeWidth = 5,
}: ScoreGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (animatedScore / 100) * circumference;
  const color = getScoreColor(score);
  const glow = getScoreGlow(score);

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(score), 100);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        filter: `drop-shadow(0 0 8px ${glow})`,
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
        />
        {/* Progress arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{
            transition: 'stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />
      </svg>
      {/* Center text */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
        }}
      >
        <span
          style={{
            fontSize: size * 0.28,
            fontWeight: 800,
            color,
            lineHeight: 1,
            fontFamily: "'Inter', sans-serif",
          }}
        >
          {Math.round(animatedScore)}
        </span>
        <span
          style={{
            fontSize: size * 0.13,
            color: 'var(--text-muted)',
            fontWeight: 500,
            marginTop: 1,
          }}
        >
          match
        </span>
      </div>
    </div>
  );
}
