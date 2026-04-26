import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, X, Type, File } from 'lucide-react';

interface JDUploaderProps {
  jdText: string;
  onJdTextChange: (text: string) => void;
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  onClearFile: () => void;
  isLoading: boolean;
}

type InputMode = 'text' | 'file';

export default function JDUploader({
  jdText,
  onJdTextChange,
  onFileSelect,
  selectedFile,
  onClearFile,
  isLoading,
}: JDUploaderProps) {
  const [mode, setMode] = useState<InputMode>('text');

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0]);
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
    disabled: isLoading,
  });

  return (
    <div>
      {/* Mode toggle */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          marginBottom: 16,
          background: 'var(--bg-input)',
          borderRadius: 10,
          padding: 4,
        }}
      >
        <button
          onClick={() => setMode('text')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '8px 16px',
            borderRadius: 8,
            border: 'none',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: "'Inter', sans-serif",
            background: mode === 'text' ? 'var(--accent-indigo)' : 'transparent',
            color: mode === 'text' ? 'white' : 'var(--text-muted)',
            transition: 'all 0.2s ease',
          }}
        >
          <Type size={14} />
          Paste Text
        </button>
        <button
          onClick={() => setMode('file')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '8px 16px',
            borderRadius: 8,
            border: 'none',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: "'Inter', sans-serif",
            background: mode === 'file' ? 'var(--accent-indigo)' : 'transparent',
            color: mode === 'file' ? 'white' : 'var(--text-muted)',
            transition: 'all 0.2s ease',
          }}
        >
          <File size={14} />
          Upload File
        </button>
      </div>

      {/* Text mode */}
      {mode === 'text' && (
        <textarea
          className="input-field"
          placeholder="Paste job description here... (minimum 50 characters)&#10;&#10;Example: We are looking for a Senior Python Developer with 5+ years of experience in FastAPI, Docker, AWS, and PostgreSQL..."
          value={jdText}
          onChange={(e) => onJdTextChange(e.target.value)}
          disabled={isLoading}
          style={{
            minHeight: 220,
            resize: 'vertical',
            lineHeight: 1.6,
          }}
        />
      )}

      {/* File mode */}
      {mode === 'file' && (
        <>
          {selectedFile ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '16px 20px',
                background: 'rgba(99,102,241,0.08)',
                border: '1px solid rgba(99,102,241,0.2)',
                borderRadius: 12,
              }}
            >
              <FileText size={20} style={{ color: 'var(--accent-indigo-light)' }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {selectedFile.name}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </div>
              </div>
              <button
                onClick={onClearFile}
                disabled={isLoading}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                  padding: 4,
                }}
              >
                <X size={16} />
              </button>
            </div>
          ) : (
            <div
              {...getRootProps()}
              className={`dropzone ${isDragActive ? 'active' : ''}`}
            >
              <input {...getInputProps()} />
              <Upload
                size={32}
                style={{
                  color: isDragActive
                    ? 'var(--accent-indigo)'
                    : 'var(--text-muted)',
                  marginBottom: 12,
                }}
              />
              <p
                style={{
                  fontSize: 14,
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                }}
              >
                {isDragActive
                  ? 'Drop your file here...'
                  : 'Drag & drop a JD file, or click to browse'}
              </p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                PDF, DOCX, or TXT — Max 10MB
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
