import { useState, useCallback } from 'react';
import {
  ShieldCheck,
  ScanLine,
  FileCheck,
  MapPin,
  User,
  BadgeCheck,
  LogIn,
} from 'lucide-react';
import { useApp } from '@/store';
import { AuthShell, BrandPanel, Breadcrumbs, PasswordField, Captcha } from '@/components/Auth';
import type { Role } from '@/types';

export function Login() {
  const { authenticate, navigate, showToast } = useApp();
  const [role, setRole] = useState<Role>('consumer');
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [captchaOk, setCaptchaOk] = useState(false);
  const [errors, setErrors] = useState<{ id?: string | null; password?: string | null }>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const idErr = !id.trim() ? `${role === 'officer' ? 'Officer ID' : 'Aadhaar / Registered ID'} is required` : null;
      const pwErr = !password ? 'Password is required' : null;
      setErrors({ id: idErr, password: pwErr });
      if (idErr || pwErr) return;
      if (!captchaOk) {
        showToast('error', 'Please complete the CAPTCHA.');
        return;
      }

      setSubmitting(true);
      void authenticate(id.trim(), password, role).finally(() => setSubmitting(false));
    },
    [role, id, password, captchaOk, authenticate, showToast]
  );

  const idLabel = role === 'officer' ? 'Officer ID' : 'Aadhaar / Registered ID';
  const idPlaceholder = role === 'officer' ? 'e.g. OFFICER001' : 'e.g. consumer@test.com';

  return (
    <AuthShell
      brandSide={
        <BrandPanel
          title="Verify packaged commodity compliance with confidence."
          subtitle="NIRIKSHA helps consumers and officers check product labels against Legal Metrology requirements using AI."
          features={[
            { icon: <ScanLine className="w-4 h-4 text-white" />, text: 'AI-powered label scanning & compliance checks' },
            { icon: <FileCheck className="w-4 h-4 text-white" />, text: 'Instant violation detection and reports' },
            { icon: <MapPin className="w-4 h-4 text-white" />, text: 'Zone-wise violation mapping for officers' },
          ]}
        />
      }
    >
      {/* Mobile brand */}
      <div className="lg:hidden flex items-center gap-2.5 mb-6">
        <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="font-display font-extrabold text-ink-900 text-lg leading-none">NIRIKSHA</p>
          <p className="text-[11px] text-ink-500 mt-1 leading-none">AI-Powered Product Compliance</p>
        </div>
      </div>

      <Breadcrumbs items={[{ label: 'Home' }, { label: 'Sign In', active: true }]} />

      {/* Role toggle */}
      <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-ink-100 mb-6">
        <button
          type="button"
          onClick={() => {
            setRole('consumer');
            setId('');
            setPassword('');
            setErrors({});
          }}
          className={`flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${
            role === 'consumer' ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500'
          }`}
        >
          <User className="w-4 h-4" /> Consumer
        </button>
        <button
          type="button"
          onClick={() => {
            setRole('officer');
            setId('');
            setPassword('');
            setErrors({});
          }}
          className={`flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${
            role === 'officer' ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500'
          }`}
        >
          <BadgeCheck className="w-4 h-4" /> Officer
        </button>
      </div>

      <h1 className="text-2xl font-bold text-ink-900">
        Sign in to NIRIKSHA
      </h1>
      <p className="text-ink-500 mt-1 text-sm">
        Access your product compliance and verification dashboard.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label className="label">{idLabel}</label>
          <input
            className={`input ${errors.id ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
            value={id}
            onChange={(e) => setId(e.target.value)}
            placeholder={idPlaceholder}
            autoComplete="username"
          />
          {errors.id && <p className="text-xs text-danger-600 mt-1">{errors.id}</p>}
        </div>

        <PasswordField
          label="Password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          placeholder="Enter your password"
          autoComplete="current-password"
        />

        <Captcha onVerify={setCaptchaOk} />

        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2 cursor-pointer text-ink-600">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="rounded border-ink-300 text-brand-600 focus:ring-brand-500"
            />
            Remember me
          </label>
          <button type="button" className="text-brand-600 font-medium hover:text-brand-700">
            Forgot Password?
          </button>
        </div>

        <button type="submit" disabled={submitting} className="btn-primary w-full py-3">
          <LogIn className="w-4 h-4" />
          {submitting ? 'Signing in…' : 'Sign In'}
        </button>
      </form>

      {/* Demo credentials */}
      <div className="mt-5 rounded-xl bg-brand-50 border border-brand-100 p-3.5 text-xs text-brand-800">
        <p className="font-semibold mb-1">Demo credentials</p>
        {role === 'consumer' ? (
          <p>ID: <span className="font-mono">user123</span> • Password: <span className="font-mono">123456</span></p>
        ) : (
          <p>ID: <span className="font-mono">officer123</span> • Password: <span className="font-mono">123456</span></p>
        )}
      </div>

      <p className="text-center text-sm text-ink-500 mt-6">
        Don't have an account?{' '}
        <button
          onClick={() => navigate('signup')}
          className="text-brand-600 font-semibold hover:text-brand-700"
        >
          Create {role === 'officer' ? 'Officer' : 'Consumer'} Account
        </button>
      </p>
    </AuthShell>
  );
}
