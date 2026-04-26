import { Download } from 'lucide-react';

interface ExportButtonProps {
  searchEventId: string;
}

export default function ExportButton({ searchEventId }: ExportButtonProps) {
  const handleExport = () => {
    const baseUrl = import.meta.env.VITE_API_URL || '/api/v1';
    window.open(`${baseUrl}/search/${searchEventId}/export`, '_blank');
  };

  return (
    <button
      className="btn-secondary"
      onClick={handleExport}
      style={{ fontSize: 12 }}
    >
      <Download size={14} />
      Export CSV
    </button>
  );
}
