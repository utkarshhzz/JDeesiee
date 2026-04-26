import { History, Clock, Zap, ChevronRight } from 'lucide-react';
import { useSearchHistory } from '../hooks/useSearchHistory';

interface SearchHistorySidebarProps {
  onSelectJd: (jdText: string) => void;
}

export default function SearchHistorySidebar({ onSelectJd }: SearchHistorySidebarProps) {
  const { data, isLoading } = useSearchHistory();

  if (isLoading) {
    return (
      <div style={{ padding: 16 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 16,
          }}
        >
          <History size={16} style={{ color: 'var(--accent-indigo-light)' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>
            RECENT SEARCHES
          </span>
        </div>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="skeleton"
            style={{ height: 64, marginBottom: 8, borderRadius: 10 }}
          />
        ))}
      </div>
    );
  }

  const history = data?.history ?? [];

  return (
    <div style={{ padding: 16 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 16,
        }}
      >
        <History size={16} style={{ color: 'var(--accent-indigo-light)' }} />
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--text-secondary)',
            letterSpacing: '0.05em',
          }}
        >
          RECENT SEARCHES
        </span>
        {history.length > 0 && (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: 11,
              color: 'var(--text-muted)',
            }}
          >
            {history.length}
          </span>
        )}
      </div>

      {history.length === 0 ? (
        <p style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>
          No searches yet
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {history.map((item) => (
            <button
              key={item.search_event_id}
              onClick={() => onSelectJd(item.jd_snippet)}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '10px 12px',
                background: 'var(--bg-input)',
                border: '1px solid transparent',
                borderRadius: 10,
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'all 0.2s ease',
                fontFamily: "'Inter', sans-serif",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-card-hover)';
                e.currentTarget.style.borderColor = 'var(--border-color)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--bg-input)';
                e.currentTarget.style.borderColor = 'transparent';
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <p
                  style={{
                    fontSize: 12,
                    color: 'var(--text-primary)',
                    lineHeight: 1.4,
                    marginBottom: 4,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}
                >
                  {item.jd_snippet || 'Untitled search'}
                </p>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  {item.total_latency_ms != null && (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        fontSize: 11,
                        color: 'var(--text-muted)',
                      }}
                    >
                      <Clock size={10} />
                      {item.total_latency_ms}ms
                    </span>
                  )}
                  {item.embedding_cached && (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        fontSize: 10,
                        color: 'var(--accent-emerald)',
                        fontWeight: 600,
                      }}
                    >
                      <Zap size={10} />
                      Cached
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight
                size={14}
                style={{ color: 'var(--text-muted)', marginTop: 2, flexShrink: 0 }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
