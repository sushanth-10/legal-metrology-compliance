import { useState } from 'react';
import { Download, Eye, FileText, X } from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader, StatusBadge } from '@/components/ui';
import { downloadReportAsPdf } from '@/lib/reporting';
import type { GeneratedReport } from '@/types';

export function Reports() {
  const { reports, setPage } = useApp();
  const [previewReport, setPreviewReport] = useState<GeneratedReport | null>(null);

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Generated formal compliance reports from completed scan results."
        actions={
          <button onClick={() => setPage('history')} className="btn-secondary">
            <FileText className="w-4 h-4" /> View scan history
          </button>
        }
      />

      {reports.length === 0 ? (
        <div className="card p-8 text-center">
          <FileText className="w-10 h-10 text-ink-300 mx-auto" />
          <h3 className="font-semibold text-ink-900 mt-4">No generated reports yet</h3>
          <p className="text-sm text-ink-500 mt-2 max-w-md mx-auto">
            Generate a PDF report from an officer-approved scan result to see it here.
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-ink-50">
                <tr>
                  <th className="table-th">Report</th>
                  <th className="table-th">Product</th>
                  <th className="table-th">Date</th>
                  <th className="table-th">Status</th>
                  <th className="table-th text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {reports.map((report) => (
                  <tr key={report.id} className="hover:bg-ink-50/60">
                    <td className="table-td">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-ink-400" />
                        <span className="font-medium text-ink-800">{report.id}</span>
                      </div>
                    </td>
                    <td className="table-td">{report.productName}</td>
                    <td className="table-td text-ink-500">{new Date(report.generatedAt).toLocaleString()}</td>
                    <td className="table-td"><StatusBadge status={report.overallStatus} /></td>
                    <td className="table-td text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => setPreviewReport(report)} className="btn-secondary px-3 py-1.5 text-xs">
                          <Eye className="w-3.5 h-3.5" /> View Report
                        </button>
                        <button onClick={() => downloadReportAsPdf(report)} className="btn-secondary px-3 py-1.5 text-xs">
                          <Download className="w-3.5 h-3.5" /> Download PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {previewReport && (
        <div className="fixed inset-0 z-50 bg-ink-950/70 flex items-center justify-center p-4">
          <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl border border-ink-200 bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-500">Report preview</p>
                <h3 className="font-semibold text-ink-900 text-xl mt-1">{previewReport.reportTitle}</h3>
              </div>
              <button onClick={() => setPreviewReport(null)} className="btn-secondary px-3 py-2">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-5 rounded-xl bg-ink-50 border border-ink-200 p-4 text-sm text-ink-700">
              <div className="grid sm:grid-cols-2 gap-3">
                <div><span className="font-semibold text-ink-800">Application:</span> {previewReport.applicationName}</div>
                <div><span className="font-semibold text-ink-800">Generated:</span> {new Date(previewReport.generatedAt).toLocaleString()}</div>
                <div><span className="font-semibold text-ink-800">Product:</span> {previewReport.productName}</div>
                <div><span className="font-semibold text-ink-800">Status:</span> {previewReport.overallStatus}</div>
              </div>
              <div className="mt-4 grid sm:grid-cols-3 gap-3 text-xs">
                <div className="rounded-lg bg-danger-50 p-2 text-danger-700"><strong>Violations:</strong> {previewReport.summary.violations}</div>
                <div className="rounded-lg bg-warning-50 p-2 text-warning-700"><strong>Review:</strong> {previewReport.summary.review}</div>
                <div className="rounded-lg bg-success-50 p-2 text-success-700"><strong>Compliant:</strong> {previewReport.summary.compliant}</div>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {previewReport.checks.map((check) => (
                <div key={check.id} className="rounded-xl border border-ink-200 p-4">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <p className="font-semibold text-ink-900">{check.name}</p>
                    <span className={`badge text-[10px] ${
                      check.status === 'compliant'
                        ? 'bg-success-50 text-success-700'
                        : check.status === 'non-compliant'
                        ? 'bg-danger-50 text-danger-700'
                        : 'bg-warning-50 text-warning-700'
                    }`}>
                      {check.status.replace('-', ' ')}
                    </span>
                  </div>
                  <div className="mt-3 text-sm text-ink-700 space-y-2">
                    <p><span className="font-semibold text-ink-800">Extracted declaration/value:</span> {check.value}</p>
                    <p><span className="font-semibold text-ink-800">Applicable requirement/rule:</span> {check.requirement}</p>
                    <p><span className="font-semibold text-ink-800">Explanation:</span> {check.explanation}</p>
                    <p><span className="font-semibold text-ink-800">Evidence/source:</span> {check.evidence}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-5 flex flex-col sm:flex-row gap-3 justify-end">
              <button onClick={() => downloadReportAsPdf(previewReport)} className="btn-primary py-2.5">
                <Download className="w-4 h-4" /> Download PDF
              </button>
              <button onClick={() => setPreviewReport(null)} className="btn-secondary py-2.5">
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
