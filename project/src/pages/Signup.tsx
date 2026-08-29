import { User, BadgeCheck, ShieldCheck, ArrowRight, ArrowLeft } from 'lucide-react';
import { useApp } from '@/store';
import { AuthShell, BrandPanel, Breadcrumbs } from '@/components/Auth';

export function Signup() {
  const { navigate } = useApp();

  return (
    <AuthShell
      brandSide={
        <BrandPanel
          title="Join NIRIKSHA to verify product compliance."
          subtitle="Create an account to scan packaged products, report violations, and access compliance tools."
          features={[
            { icon: <User className="w-4 h-4 text-white" />, text: 'Consumer accounts for product verification' },
            { icon: <BadgeCheck className="w-4 h-4 text-white" />, text: 'Officer accounts for field inspections' },
            { icon: <ShieldCheck className="w-4 h-4 text-white" />, text: 'Secure, role-based access control' },
          ]}
        />
      }
    >
      <div className="lg:hidden flex items-center gap-2.5 mb-6">
        <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="font-display font-extrabold text-ink-900 text-lg leading-none">NIRIKSHA</p>
          <p className="text-[11px] text-ink-500 mt-1 leading-none">AI-Powered Product Compliance</p>
        </div>
      </div>

      <Breadcrumbs items={[{ label: 'Home' }, { label: 'Sign Up', active: true }]} />

      <h1 className="text-2xl font-bold text-ink-900">Create your NIRIKSHA Account</h1>
      <p className="text-ink-500 mt-1 text-sm">Select your account type to continue.</p>

      <div className="mt-6 space-y-4">
        {/* Consumer card */}
        <button
          onClick={() => navigate('signup-consumer')}
          className="card card-hover w-full p-5 text-left flex items-start gap-4 group"
        >
          <div className="w-12 h-12 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0">
            <User className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-ink-900">Consumer</h3>
            <p className="text-sm text-ink-500 mt-1">
              For citizens and consumers who want to verify packaged products or report violations.
            </p>
            <span className="inline-flex items-center gap-1.5 text-brand-600 font-semibold text-sm mt-3 group-hover:gap-2.5 transition-all">
              Register as Consumer <ArrowRight className="w-4 h-4" />
            </span>
          </div>
        </button>

        {/* Officer card */}
        <button
          onClick={() => navigate('signup-officer')}
          className="card card-hover w-full p-5 text-left flex items-start gap-4 group"
        >
          <div className="w-12 h-12 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0">
            <BadgeCheck className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-ink-900">Officer</h3>
              <span className="badge bg-brand-50 text-brand-700 text-[10px]">Restricted</span>
            </div>
            <p className="text-sm text-ink-500 mt-1">
              For authorized Legal Metrology officers conducting product compliance inspections.
            </p>
            <span className="inline-flex items-center gap-1.5 text-brand-600 font-semibold text-sm mt-3 group-hover:gap-2.5 transition-all">
              Register as Officer <ArrowRight className="w-4 h-4" />
            </span>
          </div>
        </button>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <button onClick={() => navigate('login')} className="btn-ghost text-ink-500 text-sm">
          <ArrowLeft className="w-4 h-4" /> Back to Sign In
        </button>
        <p className="text-sm text-ink-500">
          Already have an account?{' '}
          <button onClick={() => navigate('login')} className="text-brand-600 font-semibold hover:text-brand-700">
            Sign In
          </button>
        </p>
      </div>
    </AuthShell>
  );
}
