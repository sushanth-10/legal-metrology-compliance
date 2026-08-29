import { useEffect, useState } from 'react';
import { ShieldCheck, CheckCircle2, XCircle, Info, X } from 'lucide-react';
import { useApp } from '@/store';

export function ToastHost() {
  const { toasts, dismissToast } = useApp();

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-[calc(100%-2rem)] sm:w-auto">
      {toasts.map((t) => {
        const cfg =
          t.type === 'success'
            ? { icon: CheckCircle2, ring: 'border-success-200', bg: 'bg-success-50', text: 'text-success-800' }
            : t.type === 'error'
            ? { icon: XCircle, ring: 'border-danger-200', bg: 'bg-danger-50', text: 'text-danger-800' }
            : { icon: Info, ring: 'border-brand-200', bg: 'bg-brand-50', text: 'text-brand-800' };
        return (
          <div
            key={t.id}
            className={`animate-fade-in flex items-start gap-2.5 rounded-xl border ${cfg.ring} ${cfg.bg} px-4 py-3 shadow-pop`}
          >
            <cfg.icon className={`w-5 h-5 shrink-0 mt-0.5 ${cfg.text}`} />
            <p className={`text-sm font-medium ${cfg.text} flex-1`}>{t.message}</p>
            <button onClick={() => dismissToast(t.id)} className={`${cfg.text} opacity-60 hover:opacity-100`}>
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function PasswordField({
  label,
  value,
  onChange,
  error,
  placeholder,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string | null;
  placeholder?: string;
  autoComplete?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="label">{label}</label>
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          className={`input pr-11 ${error ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-600 text-xs font-semibold"
        >
          {show ? 'Hide' : 'Show'}
        </button>
      </div>
      {error && <p className="text-xs text-danger-600 mt-1">{error}</p>}
    </div>
  );
}

export function FieldError({ error }: { error?: string | null }) {
  if (!error) return null;
  return <p className="text-xs text-danger-600 mt-1">{error}</p>;
}

export function Breadcrumbs({ items }: { items: { label: string; active?: boolean }[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-ink-500 mb-5 flex-wrap">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-ink-300">›</span>}
          <span className={item.active ? 'text-ink-800 font-medium' : ''}>{item.label}</span>
        </span>
      ))}
    </nav>
  );
}

export function AuthFooter() {
  return (
    <footer className="border-t border-ink-200 bg-white">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="font-display font-bold text-ink-900 text-sm leading-none">NIRIKSHA</p>
              <p className="text-[11px] text-ink-500 mt-0.5 leading-none">
                AI-Powered Product Compliance
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-ink-500">
            <a href="#" className="hover:text-brand-600">Privacy Policy</a>
            <a href="#" className="hover:text-brand-600">Terms of Use</a>
            <a href="#" className="hover:text-brand-600">Help</a>
            <a href="#" className="hover:text-brand-600">Contact</a>
          </div>
        </div>
        <div className="mt-5 pt-5 border-t border-ink-100 text-center">
          <p className="text-sm text-ink-500">
            NIRIKSHA – AI-Powered Product Compliance
          </p>
          <p className="text-xs text-ink-400 mt-1">
            Designed for product compliance and consumer protection.
          </p>
        </div>
      </div>
    </footer>
  );
}

export function AuthShell({
  children,
  brandSide,
}: {
  children: React.ReactNode;
  brandSide: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-ink-50">
      <div className="flex-1 grid lg:grid-cols-2">
        {/* Brand panel */}
        <div className="hidden lg:flex flex-col justify-between p-10 bg-gradient-to-br from-brand-700 to-brand-900 text-white relative overflow-hidden">
          {brandSide}
        </div>
        {/* Form panel */}
        <div className="flex flex-col">
          <div className="flex-1 flex items-center justify-center px-5 sm:px-8 py-10">
            <div className="w-full max-w-md">{children}</div>
          </div>
        </div>
      </div>
      <AuthFooter />
    </div>
  );
}

export function BrandPanel({
  title,
  subtitle,
  features,
}: {
  title: string;
  subtitle: string;
  features: { icon: React.ReactNode; text: string }[];
}) {
  return (
    <>
      <div className="absolute -right-12 -top-12 w-64 h-64 rounded-full bg-white/5" />
      <div className="absolute -left-16 bottom-10 w-48 h-48 rounded-full bg-white/5" />
      <div className="relative">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-white/15 flex items-center justify-center backdrop-blur">
            <ShieldCheck className="w-6 h-6 text-white" strokeWidth={2.2} />
          </div>
          <div>
            <p className="font-display font-extrabold text-2xl tracking-tight">NIRIKSHA</p>
            <p className="text-brand-100 text-sm mt-0.5">AI-Powered Product Compliance</p>
          </div>
        </div>
        <div className="mt-16 max-w-sm">
          <h2 className="text-3xl font-bold leading-tight">{title}</h2>
          <p className="text-brand-100 mt-3">{subtitle}</p>
        </div>
        <ul className="mt-10 space-y-4 max-w-sm">
          {features.map((f, i) => (
            <li key={i} className="flex items-center gap-3 text-brand-50">
              <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center shrink-0">
                {f.icon}
              </div>
              <span className="text-sm">{f.text}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="relative text-brand-200 text-xs">
        Designed for product compliance and consumer protection.
      </p>
    </>
  );
}

export function Captcha({ onVerify }: { onVerify: (ok: boolean) => void }) {
  const [a] = useState(() => Math.floor(Math.random() * 8) + 1);
  const [b] = useState(() => Math.floor(Math.random() * 8) + 1);
  const [answer, setAnswer] = useState('');
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    const ok = parseInt(answer, 10) === a + b;
    setVerified(ok);
    onVerify(ok);
  }, [answer, a, b, onVerify]);

  return (
    <div>
      <label className="label">CAPTCHA</label>
      <div
        className={`flex items-center gap-3 rounded-xl border px-3.5 py-2.5 transition-colors ${
          verified ? 'border-success-300 bg-success-50' : 'border-ink-200 bg-white'
        }`}
      >
        <span className="text-sm font-semibold text-ink-700 select-none">
          {a} + {b} =
        </span>
        <input
          type="number"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          className="w-16 border-0 bg-transparent text-sm focus:ring-0 p-0 outline-none"
          placeholder="?"
          inputMode="numeric"
        />
        {verified && <CheckCircle2 className="w-4 h-4 text-success-500 ml-auto" />}
      </div>
      {!verified && answer && <p className="text-xs text-danger-600 mt-1">Incorrect answer</p>}
    </div>
  );
}
