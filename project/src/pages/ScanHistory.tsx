import { useState, useMemo } from 'react';
import { Search, Filter, ArrowLeft, Calendar, Tag, AlertTriangle } from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader, StatusBadge, EmptyState } from '@/components/ui';
import { Result } from '@/pages/Result';
import type { ComplianceStatus } from '@/types';

const statusOptions: { value: ComplianceStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All Status' },
  { value: 'compliant', label: 'Compliant' },
  { value: 'non-compliant', label: 'Non-Compliant' },
  { value: 'needs-review', label: 'Needs Review' },
];

export function ScanHistory() {
  const { scans, selectedScanId, setSelectedScanId } = useApp();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<ComplianceStatus | 'all'>('all');
  const [date, setDate] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const selected = scans.find((s) => s.id === selectedScanId);

  const filtered = useMemo(() => {
    return scans.filter((s) => {
      if (query && !s.product.toLowerCase().includes(query.toLowerCase())) return false;
      if (status !== 'all' && s.status !== status) return false;
      if (date && !s.date.toLowerCase().includes(date.toLowerCase())) return false;
      return true;
    });
  }, [scans, query, status, date]);

  if (selected) {
    return (
      <div>
        <button
          onClick={() => setSelectedScanId(null)}
          className="btn-ghost text-brand-600 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to History
        </button>
        <Result onScanAnother={() => setSelectedScanId(null)} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Scan History"
        subtitle="Review and filter all your previous compliance scans."
      />

      {/* Filters */}
      <div className="card p-4 mb-5">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by product name…"
              className="input pl-9"
            />
          </div>
          <button
            onClick={() => setShowFilters((s) => !s)}
            className="btn-secondary sm:hidden justify-center"
          >
            <Filter className="w-4 h-4" /> Filters
          </button>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as ComplianceStatus | 'all')}
            className="input sm:w-44 hidden sm:block"
          >
            {statusOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            placeholder="Filter by date"
            className="input sm:w-40 hidden sm:block"
          />
        </div>
        {showFilters && (
          <div className="grid grid-cols-2 gap-3 mt-3 sm:hidden animate-fade-in">
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as ComplianceStatus | 'all')}
              className="input"
            >
              {statusOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              placeholder="Date"
              className="input"
            />
          </div>
        )}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<Search className="w-6 h-6" />}
          title="No scans found"
          description="Try adjusting your search or filters to find the scan you're looking for."
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="card overflow-hidden hidden md:block">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-ink-50">
                  <tr>
                    <th className="table-th">Product</th>
                    <th className="table-th">Scan Date</th>
                    <th className="table-th">Status</th>
                    <th className="table-th">Violations</th>
                    <th className="table-th text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {filtered.map((s) => (
                    <tr key={s.id} className="hover:bg-ink-50/60">
                      <td className="table-td">
                        <div className="flex items-center gap-3">
                          <img
                            src={s.image}
                            alt={s.product}
                            className="w-10 h-10 rounded-lg object-cover"
                          />
                          <div>
                            <p className="font-medium text-ink-800">{s.product}</p>
                            {s.category && (
                              <p className="text-xs text-ink-500 flex items-center gap-1 mt-0.5">
                                <Tag className="w-3 h-3" /> {s.category}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="table-td text-ink-500">
                        <span className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5" /> {s.date}
                        </span>
                      </td>
                      <td className="table-td">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="table-td">
                        {s.violations > 0 ? (
                          <span className="inline-flex items-center gap-1 font-semibold text-danger-600">
                            <AlertTriangle className="w-3.5 h-3.5" /> {s.violations}
                          </span>
                        ) : (
                          <span className="text-ink-400">0</span>
                        )}
                      </td>
                      <td className="table-td text-right">
                        <button
                          onClick={() => setSelectedScanId(s.id)}
                          className="btn-secondary px-3 py-1.5 text-xs"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {filtered.map((s) => (
              <div key={s.id} className="card p-4 flex gap-3">
                <img
                  src={s.image}
                  alt={s.product}
                  className="w-16 h-16 rounded-lg object-cover shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold text-ink-800 truncate">{s.product}</p>
                    <StatusBadge status={s.status} />
                  </div>
                  <p className="text-xs text-ink-500 mt-1">{s.date}</p>
                  <div className="flex items-center justify-between mt-2.5">
                    <span className="text-xs text-ink-500">
                      Violations:{' '}
                      <b className={s.violations > 0 ? 'text-danger-600' : 'text-ink-700'}>
                        {s.violations}
                      </b>
                    </span>
                    <button
                      onClick={() => setSelectedScanId(s.id)}
                      className="btn-secondary px-3 py-1.5 text-xs"
                    >
                      View Details
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
