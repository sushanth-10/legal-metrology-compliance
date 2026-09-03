import {
  Upload,
  Camera,
  ScanLine,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
  TrendingUp,
  Activity,
} from 'lucide-react';
import { useApp } from '@/store';
import { StatusBadge } from '@/components/ui';
import { Logo } from '@/components/Logo';

export function Dashboard() {
  const { user, role, scans, scansLoading, setPage, setSelectedScanId } = useApp();

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const recent = scans.slice(0, 5);
  const stats = [
    { label: 'Total Scans', value: scans.length, icon: ScanLine, tint: 'bg-brand-50 text-brand-600' },
    { label: 'Compliant', value: scans.filter((scan) => scan.status === 'compliant').length, icon: CheckCircle2, tint: 'bg-success-50 text-success-600' },
    { label: 'Violations Found', value: scans.reduce((total, scan) => total + Math.max(0, scan.violations || 0), 0), icon: XCircle, tint: 'bg-danger-50 text-danger-600' },
    { label: 'Needs Review', value: scans.filter((scan) => scan.status === 'needs-review').length, icon: AlertCircle, tint: 'bg-warning-50 text-warning-600' },
  ];

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-900">
          {greeting}, {user.name.split(' ')[0]}
        </h1>
        <p className="text-ink-500 mt-1 text-sm sm:text-base">
          Monitor and verify packaged commodity compliance.
        </p>
      </div>

      {/* Primary scan card */}
      <div className="card p-6 sm:p-8 bg-gradient-to-br from-brand-600 to-brand-700 text-white border-brand-700 relative overflow-hidden">
        <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-white/10" />
        <div className="absolute -right-16 bottom-0 w-32 h-32 rounded-full bg-white/5" />
        <div className="relative">
          <div className="flex items-center gap-2 text-brand-100 text-xs font-semibold uppercase tracking-wider">
            <ScanLine className="w-4 h-4" /> AI Compliance Scan
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold mt-2">Scan a Product</h2>
          <p className="text-brand-100 mt-2 max-w-xl text-sm sm:text-base">
            Upload a product label or capture an image to perform an AI-powered compliance check.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 mt-5">
            <button
              onClick={() => setPage('scan')}
              className="btn bg-white text-brand-700 hover:bg-brand-50 px-5 py-3 font-semibold shadow-sm"
            >
              <Upload className="w-4 h-4" /> Upload Image
            </button>
            <button
              onClick={() => setPage('scan')}
              className="btn bg-brand-800/40 text-white border border-white/30 hover:bg-brand-800/60 px-5 py-3"
            >
              <Camera className="w-4 h-4" /> Take Photo
            </button>
          </div>
          <p className="text-brand-100/80 text-xs mt-4 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" />
            Use a clear image of the product label for better analysis.
          </p>
        </div>
        <div className="relative mt-6 w-44 rounded-xl bg-white p-3 shadow-lg ring-1 ring-white/30 sm:absolute sm:right-8 sm:top-1/2 sm:mt-0 sm:-translate-y-1/2">
          <Logo className="h-auto w-full" />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="card card-hover p-5">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${s.tint}`}>
              <s.icon className="w-5 h-5" />
            </div>
            <p className="text-3xl font-bold text-ink-900 mt-3">{scansLoading ? '—' : s.value}</p>
            <p className="text-sm text-ink-500 mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Recent scans */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-ink-200">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-ink-500" />
            <h3 className="font-semibold text-ink-900">Recent Scans</h3>
          </div>
          <button
            onClick={() => setPage('history')}
            className="btn-ghost text-brand-600 hover:bg-brand-50 text-sm"
          >
            View all <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Desktop table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full">
            <thead className="bg-ink-50">
              <tr>
                <th className="table-th">Product</th>
                <th className="table-th">Date &amp; Time</th>
                <th className="table-th">Compliance Status</th>
                <th className="table-th">Violations</th>
                <th className="table-th text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={5} className="table-td text-center text-ink-500 py-8">
                    {scansLoading ? 'Loading scans…' : 'No scans recorded yet.'}
                  </td>
                </tr>
              ) : recent.map((s) => (
                <tr key={s.id} className="hover:bg-ink-50/60">
                  <td className="table-td">
                    <div className="flex items-center gap-3">
                      <img
                        src={s.image}
                        alt={s.product}
                        className="w-9 h-9 rounded-lg object-cover"
                      />
                      <span className="font-medium text-ink-800">{s.product}</span>
                    </div>
                  </td>
                  <td className="table-td text-ink-500">{s.date}</td>
                  <td className="table-td">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="table-td">
                    <span
                      className={`font-semibold ${
                        s.violations > 0 ? 'text-danger-600' : 'text-ink-700'
                      }`}
                    >
                      {s.violations}
                    </span>
                  </td>
                  <td className="table-td text-right">
                    <button
                      onClick={() => {
                        setSelectedScanId(s.id);
                        setPage('history');
                      }}
                      className="btn-secondary px-3 py-1.5 text-xs"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="md:hidden divide-y divide-ink-100">
          {recent.length === 0 ? (
            <p className="p-6 text-center text-sm text-ink-500">
              {scansLoading ? 'Loading scans…' : 'No scans recorded yet.'}
            </p>
          ) : recent.map((s) => (
            <div key={s.id} className="p-4 flex gap-3">
              <img src={s.image} alt={s.product} className="w-14 h-14 rounded-lg object-cover" />
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-ink-800 truncate">{s.product}</p>
                  <StatusBadge status={s.status} />
                </div>
                <p className="text-xs text-ink-500 mt-1">{s.date}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-ink-500">
                    Violations: <b className="text-ink-700">{s.violations}</b>
                  </span>
                  <button
                    onClick={() => {
                      setSelectedScanId(s.id);
                      setPage('history');
                    }}
                    className="btn-secondary px-3 py-1.5 text-xs"
                  >
                    View Details
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {role === 'officer' && (
        <div className="card p-5 flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-ink-900">Zone activity is up 12% this week</p>
            <p className="text-sm text-ink-500">
              28 inspections completed. Review the analytics dashboard for details.
            </p>
          </div>
          <button
            onClick={() => setPage('analytics')}
            className="btn-secondary hidden sm:inline-flex"
          >
            Open Analytics
          </button>
        </div>
      )}
    </div>
  );
}
