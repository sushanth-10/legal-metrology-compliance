import {
  Mail,
  MapPin,
  Calendar,
  ShieldCheck,
  BadgeCheck,
  ScanLine,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Edit3,
} from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader } from '@/components/ui';

export function Profile() {
  const { user, role, scans } = useApp();
  const compliant = scans.filter((s) => s.status === 'compliant').length;
  const violations = scans.filter((s) => s.status === 'non-compliant').length;
  const review = scans.filter((s) => s.status === 'needs-review').length;

  return (
    <div className="max-w-4xl mx-auto">
      <PageHeader title="Profile" subtitle="Your account and compliance activity." />

      <div className="card overflow-hidden mb-6">
        <div className="h-24 bg-gradient-to-r from-brand-600 to-brand-700" />
        <div className="px-5 sm:px-6 pb-5 -mt-10">
          <div className="flex items-end justify-between">
            <div className="w-20 h-20 rounded-2xl bg-white p-1 shadow-card">
              <div className="w-full h-full rounded-xl bg-brand-600 text-white flex items-center justify-center font-bold text-xl">
                {user.name.split(' ').map((w) => w[0]).join('').slice(0, 2)}
              </div>
            </div>
            <button className="btn-secondary mb-1">
              <Edit3 className="w-4 h-4" /> Edit
            </button>
          </div>
          <div className="mt-3">
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-ink-900">{user.name}</h2>
              <span className={`badge ${role === 'officer' ? 'bg-brand-50 text-brand-700' : 'bg-ink-100 text-ink-600'}`}>
                {role === 'officer' ? (
                  <>
                    <ShieldCheck className="w-3 h-3" /> Officer
                  </>
                ) : (
                  'Consumer'
                )}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-ink-500">
              <span className="flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5" /> {user.email}
              </span>
              <span className="flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5" /> {user.location}
              </span>
              <span className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" /> Joined {user.joined}
              </span>
              {user.officerId && (
                <span className="flex items-center gap-1.5">
                  <BadgeCheck className="w-3.5 h-3.5" /> ID: {user.officerId}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-5">
          <ScanLine className="w-5 h-5 text-brand-600" />
          <p className="text-2xl font-bold text-ink-900 mt-2">{scans.length}</p>
          <p className="text-sm text-ink-500">Total Scans</p>
        </div>
        <div className="card p-5">
          <CheckCircle2 className="w-5 h-5 text-success-600" />
          <p className="text-2xl font-bold text-ink-900 mt-2">{compliant}</p>
          <p className="text-sm text-ink-500">Compliant</p>
        </div>
        <div className="card p-5">
          <XCircle className="w-5 h-5 text-danger-600" />
          <p className="text-2xl font-bold text-ink-900 mt-2">{violations}</p>
          <p className="text-sm text-ink-500">Violations</p>
        </div>
        <div className="card p-5">
          <AlertCircle className="w-5 h-5 text-warning-600" />
          <p className="text-2xl font-bold text-ink-900 mt-2">{review}</p>
          <p className="text-sm text-ink-500">Needs Review</p>
        </div>
      </div>
    </div>
  );
}
