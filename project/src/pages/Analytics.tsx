import {
  ScanLine,
  CheckCircle2,
  XCircle,
  MessageSquareWarning,
  TrendingUp,
  Download,
} from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader } from '@/components/ui';
import { analyticsData } from '@/data';

const cards = [
  { label: 'Total Inspections', value: 128, icon: ScanLine, tint: 'bg-brand-50 text-brand-600' },
  { label: 'Compliant Products', value: 96, icon: CheckCircle2, tint: 'bg-success-50 text-success-600' },
  { label: 'Violations', value: 24, icon: XCircle, tint: 'bg-danger-50 text-danger-600' },
  { label: 'Complaints', value: 18, icon: MessageSquareWarning, tint: 'bg-warning-50 text-warning-600' },
];

export function Analytics() {
  const { setPage } = useApp();
  const maxTrend = Math.max(...analyticsData.trend.map((t) => t.value));
  const maxCat = Math.max(...analyticsData.categories.map((c) => c.value));
  const maxV = Math.max(...analyticsData.violationTypes.map((v) => v.value));

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Inspection and compliance trends across your zone."
        actions={
          <button className="btn-secondary">
            <Download className="w-4 h-4" /> Export
          </button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {cards.map((c) => (
          <div key={c.label} className="card p-5">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.tint}`}>
              <c.icon className="w-5 h-5" />
            </div>
            <p className="text-3xl font-bold text-ink-900 mt-3">{c.value}</p>
            <p className="text-sm text-ink-500 mt-0.5">{c.label}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Trend */}
        <div className="card p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-semibold text-ink-900">Weekly Inspection Trend</h3>
            <span className="badge bg-success-50 text-success-700">
              <TrendingUp className="w-3.5 h-3.5" /> +12%
            </span>
          </div>
          <div className="flex items-end justify-between gap-3 h-48">
            {analyticsData.trend.map((t) => (
              <div key={t.label} className="flex-1 flex flex-col items-center gap-2">
                <div className="w-full flex items-end justify-center h-full">
                  <div
                    className="w-full max-w-[40px] rounded-t-lg bg-brand-500 hover:bg-brand-600 transition-colors"
                    style={{ height: `${(t.value / maxTrend) * 100}%` }}
                    title={`${t.value} inspections`}
                  />
                </div>
                <span className="text-xs text-ink-500">{t.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Categories */}
        <div className="card p-5">
          <h3 className="font-semibold text-ink-900 mb-5">By Category</h3>
          <div className="space-y-4">
            {analyticsData.categories.map((c) => (
              <div key={c.label}>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-ink-700">{c.label}</span>
                  <span className="font-semibold text-ink-900">{c.value}</span>
                </div>
                <div className="h-2 rounded-full bg-ink-100 overflow-hidden">
                  <div
                    className={`h-full ${c.color}`}
                    style={{ width: `${(c.value / maxCat) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Violation types */}
        <div className="card p-5 lg:col-span-2">
          <h3 className="font-semibold text-ink-900 mb-5">Top Violation Types</h3>
          <div className="space-y-3">
            {analyticsData.violationTypes.map((v) => (
              <div key={v.label} className="flex items-center gap-3">
                <span className="text-sm text-ink-700 w-44 shrink-0">{v.label}</span>
                <div className="flex-1 h-2 rounded-full bg-ink-100 overflow-hidden">
                  <div
                    className="h-full bg-danger-500"
                    style={{ width: `${(v.value / maxV) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-ink-900 w-8 text-right">{v.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick links */}
        <div className="card p-5">
          <h3 className="font-semibold text-ink-900 mb-4">Quick Actions</h3>
          <div className="space-y-2">
            <button onClick={() => setPage('violation-map')} className="nav-item w-full">
              View Violation Map
            </button>
            <button onClick={() => setPage('reports')} className="nav-item w-full">
              Generate Report
            </button>
            <button onClick={() => setPage('complaints')} className="nav-item w-full">
              Review Complaints
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
