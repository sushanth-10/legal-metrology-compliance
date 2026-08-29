import type { ReactNode } from 'react';
import { CheckCircle2, XCircle, AlertCircle, Info } from 'lucide-react';
import type { ComplianceStatus } from '@/types';

export function StatusBadge({ status }: { status: ComplianceStatus }) {
  if (status === 'compliant')
    return (
      <span className="badge bg-success-50 text-success-700">
        <CheckCircle2 className="w-3.5 h-3.5" /> Compliant
      </span>
    );
  if (status === 'non-compliant')
    return (
      <span className="badge bg-danger-50 text-danger-700">
        <XCircle className="w-3.5 h-3.5" /> Non-Compliant
      </span>
    );
  return (
    <span className="badge bg-warning-50 text-warning-700">
      <AlertCircle className="w-3.5 h-3.5" /> Needs Review
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-900">{title}</h1>
        {subtitle && <p className="text-ink-500 mt-1 text-sm sm:text-base">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="card p-10 text-center flex flex-col items-center gap-3">
      <div className="w-12 h-12 rounded-full bg-ink-100 flex items-center justify-center text-ink-400">
        {icon}
      </div>
      <h3 className="font-semibold text-ink-800">{title}</h3>
      <p className="text-sm text-ink-500 max-w-sm">{description}</p>
    </div>
  );
}

export function InfoNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl bg-brand-50 border border-brand-100 px-3.5 py-3 text-sm text-brand-800">
      <Info className="w-4 h-4 mt-0.5 shrink-0 text-brand-600" />
      <div>{children}</div>
    </div>
  );
}

export function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.9 ? 'bg-success-500' : value >= 0.75 ? 'bg-brand-500' : 'bg-warning-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-ink-200 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-ink-500">{pct}%</span>
    </div>
  );
}
