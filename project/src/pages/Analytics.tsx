import { useMemo } from 'react';
import {
  ScanLine,
  CheckCircle2,
  XCircle,
  AlertCircle,
  TrendingUp,
  Download,
} from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader } from '@/components/ui';
import type { Scan } from '@/types';

type TrendPoint = { label: string; value: number };
type BreakdownPoint = { label: string; value: number; color: string };

const DAY_MS = 24 * 60 * 60 * 1000;

function scanDate(value: string): Date | null {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function dayStart(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function sameDay(left: Date, right: Date): boolean {
  return dayStart(left).getTime() === dayStart(right).getTime();
}

function formatDay(value: Date): string {
  return value.toLocaleDateString(undefined, { weekday: 'short' });
}

function getViolationRule(scan: Scan, check: NonNullable<Scan['checks']>[number]): string {
  // Persisted checks use a numeric database id plus the rule id in `label`,
  // while a newly completed scan may expose the rule id as `id`.
  const checkId = String(check.id ?? '');
  const rule = checkId && !/^\d+$/.test(checkId) ? checkId : check.label || check.id;
  if (rule) return String(rule);
  return scan.product || 'Recorded violation';
}

function csvCell(value: unknown): string {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
}

export function Analytics() {
  const { scans, scansLoading, setPage, showToast } = useApp();

  const analytics = useMemo(() => {
    const compliant = scans.filter((scan) => scan.status === 'compliant').length;
    const nonCompliant = scans.filter((scan) => scan.status === 'non-compliant').length;
    const needsReview = scans.filter((scan) => scan.status === 'needs-review').length;
    const violationFindings = scans.reduce((total, scan) => total + Math.max(0, scan.violations || 0), 0);
    const scores = scans
      .map((scan) => scan.complianceScore)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    const averageScore = scores.length > 0 ? Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length) : null;

    const today = dayStart(new Date());
    const trend: TrendPoint[] = Array.from({ length: 7 }, (_, index) => {
      const date = new Date(today.getTime() - (6 - index) * DAY_MS);
      return {
        label: formatDay(date),
        value: scans.filter((scan) => {
          const parsed = scanDate(scan.date);
          return parsed ? sameDay(parsed, date) : false;
        }).length,
      };
    });

    const currentPeriodStart = new Date(today.getTime() - 6 * DAY_MS);
    const previousPeriodStart = new Date(today.getTime() - 13 * DAY_MS);
    const currentPeriod = scans.filter((scan) => {
      const parsed = scanDate(scan.date);
      return parsed ? parsed >= currentPeriodStart && parsed < new Date(today.getTime() + DAY_MS) : false;
    }).length;
    const previousPeriod = scans.filter((scan) => {
      const parsed = scanDate(scan.date);
      return parsed ? parsed >= previousPeriodStart && parsed < currentPeriodStart : false;
    }).length;
    const trendChange = previousPeriod > 0 ? Math.round(((currentPeriod - previousPeriod) / previousPeriod) * 100) : null;

    const productCounts = new Map<string, number>();
    scans.forEach((scan) => {
      const product = scan.product?.trim() || 'Product name unavailable';
      productCounts.set(product, (productCounts.get(product) || 0) + 1);
    });
    const sortedProducts = [...productCounts.entries()].sort(([, left], [, right]) => right - left);
    const productBreakdown: BreakdownPoint[] = sortedProducts.slice(0, 5).map(([label, value], index) => ({
      label,
      value,
      color: ['bg-brand-500', 'bg-success-500', 'bg-warning-500', 'bg-danger-500', 'bg-indigo-500'][index],
    }));
    if (sortedProducts.length > 5) {
      productBreakdown.push({
        label: 'Other products',
        value: sortedProducts.slice(5).reduce((sum, [, value]) => sum + value, 0),
        color: 'bg-ink-400',
      });
    }

    const violationRules = new Map<string, number>();
    scans.forEach((scan) => {
      (scan.checks || []).forEach((check) => {
        if (check.status === 'VIOLATION') {
          const rule = getViolationRule(scan, check);
          violationRules.set(rule, (violationRules.get(rule) || 0) + 1);
        }
      });
    });
    const violationTypes = [...violationRules.entries()]
      .sort(([, left], [, right]) => right - left)
      .slice(0, 8)
      .map(([label, value]) => ({ label, value }));

    return {
      compliant,
      nonCompliant,
      needsReview,
      violationFindings,
      averageScore,
      trend,
      productBreakdown,
      violationTypes,
      currentPeriod,
      trendChange,
    };
  }, [scans]);

  const maxTrend = Math.max(1, ...analytics.trend.map((point) => point.value));
  const maxProduct = Math.max(1, ...analytics.productBreakdown.map((point) => point.value));
  const maxViolation = Math.max(1, ...analytics.violationTypes.map((point) => point.value));

  const exportAnalytics = () => {
    const header = ['Scan ID', 'Product', 'Scan Date', 'Status', 'Violations', 'Compliance Score'];
    const rows = scans.map((scan) => [scan.id, scan.product, scan.date, scan.status, scan.violations, scan.complianceScore ?? '']);
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `niriksha-analytics-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    showToast('success', `Exported ${scans.length} persisted scan${scans.length === 1 ? '' : 's'}.`);
  };

  const cards = [
    { label: 'Total Inspections', value: scans.length, icon: ScanLine, tint: 'bg-brand-50 text-brand-600' },
    { label: 'Compliant Scans', value: analytics.compliant, icon: CheckCircle2, tint: 'bg-success-50 text-success-600' },
    { label: 'Violation Findings', value: analytics.violationFindings, icon: XCircle, tint: 'bg-danger-50 text-danger-600' },
    { label: 'Scans Needing Review', value: analytics.needsReview, icon: AlertCircle, tint: 'bg-warning-50 text-warning-600' },
  ];

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Live inspection metrics calculated from the scans currently shown in Scan History."
        actions={
          <button onClick={exportAnalytics} disabled={scansLoading || scans.length === 0} className="btn-secondary disabled:opacity-50">
            <Download className="w-4 h-4" /> Export scans
          </button>
        }
      />

      {scansLoading ? (
        <div className="card p-8 text-center text-ink-500">Loading analytics from your persisted scans...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {cards.map((card) => (
              <div key={card.label} className="card p-5">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${card.tint}`}>
                  <card.icon className="w-5 h-5" />
                </div>
                <p className="text-3xl font-bold text-ink-900 mt-3">{card.value}</p>
                <p className="text-sm text-ink-500 mt-0.5">{card.label}</p>
              </div>
            ))}
          </div>

          <div className="card p-4 mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-ink-600">
            <span><strong className="text-ink-900">{analytics.nonCompliant}</strong> scan{analytics.nonCompliant === 1 ? '' : 's'} marked non-compliant</span>
            <span><strong className="text-ink-900">{analytics.currentPeriod}</strong> scan{analytics.currentPeriod === 1 ? '' : 's'} in the last 7 days</span>
            <span>{analytics.averageScore === null ? 'Average score unavailable' : <><strong className="text-ink-900">{analytics.averageScore} / 100</strong> average score</>}</span>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            <div className="card p-5 lg:col-span-2">
              <div className="flex items-center justify-between mb-5">
                <h3 className="font-semibold text-ink-900">Seven-Day Inspection Trend</h3>
                <span className={`badge ${analytics.trendChange !== null && analytics.trendChange < 0 ? 'bg-warning-50 text-warning-700' : 'bg-success-50 text-success-700'}`}>
                  <TrendingUp className="w-3.5 h-3.5" />
                  {analytics.trendChange === null ? `${analytics.currentPeriod} this period` : `${analytics.trendChange >= 0 ? '+' : ''}${analytics.trendChange}% vs prior period`}
                </span>
              </div>
              {scans.length === 0 ? (
                <p className="text-sm text-ink-500 h-48 grid place-items-center">No persisted scans are available yet.</p>
              ) : (
                <div className="flex items-end justify-between gap-3 h-48">
                  {analytics.trend.map((point) => (
                    <div key={point.label} className="flex-1 flex flex-col items-center gap-2">
                      <div className="w-full flex items-end justify-center h-full">
                        <div
                          className="w-full max-w-[40px] rounded-t-lg bg-brand-500 hover:bg-brand-600 transition-colors"
                          style={{ height: `${(point.value / maxTrend) * 100}%`, minHeight: point.value > 0 ? '4px' : '0' }}
                          title={`${point.value} inspection${point.value === 1 ? '' : 's'} on ${point.label}`}
                        />
                      </div>
                      <span className="text-xs text-ink-500">{point.label}</span>
                      <span className="text-[11px] text-ink-400">{point.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card p-5">
              <h3 className="font-semibold text-ink-900 mb-5">Scans by Product</h3>
              {analytics.productBreakdown.length === 0 ? (
                <p className="text-sm text-ink-500">No product data is available.</p>
              ) : (
                <div className="space-y-4">
                  {analytics.productBreakdown.map((point) => (
                    <div key={point.label}>
                      <div className="flex items-center justify-between text-sm mb-1.5 gap-3">
                        <span className="text-ink-700 truncate" title={point.label}>{point.label}</span>
                        <span className="font-semibold text-ink-900">{point.value}</span>
                      </div>
                      <div className="h-2 rounded-full bg-ink-100 overflow-hidden">
                        <div className={`h-full ${point.color}`} style={{ width: `${(point.value / maxProduct) * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card p-5 lg:col-span-2">
              <h3 className="font-semibold text-ink-900 mb-5">Top Violation Rules</h3>
              {analytics.violationTypes.length === 0 ? (
                <p className="text-sm text-ink-500">No persisted scan findings are marked as violations.</p>
              ) : (
                <div className="space-y-3">
                  {analytics.violationTypes.map((point) => (
                    <div key={point.label} className="flex items-center gap-3">
                      <span className="text-sm text-ink-700 w-44 shrink-0 truncate" title={point.label}>{point.label}</span>
                      <div className="flex-1 h-2 rounded-full bg-ink-100 overflow-hidden">
                        <div className="h-full bg-danger-500" style={{ width: `${(point.value / maxViolation) * 100}%` }} />
                      </div>
                      <span className="text-sm font-semibold text-ink-900 w-8 text-right">{point.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card p-5">
              <h3 className="font-semibold text-ink-900 mb-4">Quick Actions</h3>
              <div className="space-y-2">
                <button onClick={() => setPage('history')} className="nav-item w-full">Review Scan History</button>
                <button onClick={() => setPage('violation-map')} className="nav-item w-full">View Violation Map</button>
                <button onClick={() => setPage('reports')} className="nav-item w-full">Open Reports</button>
                <button onClick={() => setPage('complaints')} className="nav-item w-full">Review Complaints</button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
