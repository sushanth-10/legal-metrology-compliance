import type { GeneratedReport } from '@/types';
import { apiFetch } from '@/lib/api';

export async function downloadReportAsPdf(report: GeneratedReport): Promise<void> {
  const response = await apiFetch(`/api/reports/${encodeURIComponent(report.id)}/pdf`);
  if (!response.ok) {
    let message = 'The PDF could not be downloaded.';
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail || message;
    } catch {
      /* keep the safe fallback */
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${report.id}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
