import {
  FileText,
  Download,
  Calendar,
  Filter,
  Plus,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader, StatusBadge } from '@/components/ui';

const reportTemplates = [
  { id: 'r1', name: 'Monthly Compliance Summary', desc: 'Aggregated compliance stats for the month', icon: FileText },
  { id: 'r2', name: 'Violation Breakdown', desc: 'Detailed list of all detected violations', icon: AlertCircle },
  { id: 'r3', name: 'Zone Inspection Report', desc: 'Per-zone inspection and complaint summary', icon: Calendar },
  { id: 'r4', name: 'Product Category Report', desc: 'Compliance by product category', icon: Filter },
];

export function Reports() {
  const { scans, setPage } = useApp();

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Generate, download and manage compliance reports."
        actions={
          <button className="btn-primary">
            <Plus className="w-4 h-4" /> New Report
          </button>
        }
      />

      {/* Templates */}
      <h3 className="font-semibold text-ink-900 mb-3">Report Templates</h3>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-7">
        {reportTemplates.map((r) => (
          <div key={r.id} className="card card-hover p-5 flex flex-col gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
              <r.icon className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <p className="font-semibold text-ink-900 text-sm">{r.name}</p>
              <p className="text-xs text-ink-500 mt-1">{r.desc}</p>
            </div>
            <button className="btn-secondary w-full justify-center text-xs">
              <Download className="w-3.5 h-3.5" /> Generate
            </button>
          </div>
        ))}
      </div>

      {/* Recent reports from scans */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-ink-900">Generated Reports</h3>
        <button onClick={() => setPage('history')} className="btn-ghost text-brand-600 text-sm">
          View all scans
        </button>
      </div>

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
              {scans.map((s) => (
                <tr key={s.id} className="hover:bg-ink-50/60">
                  <td className="table-td">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-ink-400" />
                      <span className="font-medium text-ink-800">
                        RPT-{s.id.replace('sc-', '').slice(-4)}
                      </span>
                    </div>
                  </td>
                  <td className="table-td">{s.product}</td>
                  <td className="table-td text-ink-500">{s.date}</td>
                  <td className="table-td">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="table-td text-right">
                    <button className="btn-secondary px-3 py-1.5 text-xs">
                      <Download className="w-3.5 h-3.5" /> Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mt-6">
        <div className="card p-4 flex items-center gap-3">
          <CheckCircle2 className="w-8 h-8 text-success-500" />
          <div>
            <p className="text-xl font-bold text-ink-900">96</p>
            <p className="text-xs text-ink-500">Compliant reports</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3">
          <XCircle className="w-8 h-8 text-danger-500" />
          <div>
            <p className="text-xl font-bold text-ink-900">24</p>
            <p className="text-xs text-ink-500">Violation reports</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3">
          <AlertCircle className="w-8 h-8 text-warning-500" />
          <div>
            <p className="text-xl font-bold text-ink-900">8</p>
            <p className="text-xs text-ink-500">Pending review</p>
          </div>
        </div>
      </div>
    </div>
  );
}
