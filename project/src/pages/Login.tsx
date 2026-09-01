import { useState, useCallback } from 'react';
import { ShieldCheck, ScanLine, FileCheck, MapPin, BadgeCheck, LogIn, KeyRound } from 'lucide-react';
import { useApp } from '@/store';
import { AuthShell, BrandPanel, Breadcrumbs, PasswordField, Captcha } from '@/components/Auth';
import type { Role } from '@/types';

type LoginMode = 'organization' | 'officer' | 'admin';

const roleOptions: Array<{ key: LoginMode; label: string; icon: typeof ShieldCheck }> = [
  { key: 'organization', label: 'Organization', icon: ShieldCheck },
  { key: 'officer', label: 'Officer', icon: BadgeCheck },
];

export function Login({ mode = 'organization' }: { mode?: LoginMode }) {
  const { authenticate, navigate, showToast } = useApp();
  const fixedRole = mode === 'admin' ? 'admin' : null;
  const [role, setRole] = useState<LoginMode>(mode);
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [remember, setRemember] = useState(true);
  const [captchaOk, setCaptchaOk] = useState(false);
  const [errors, setErrors] = useState<{ id?: string | null; password?: string | null }>({});
  const [submitting, setSubmitting] = useState(false);
  const activeRole = fixedRole ?? role;

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const idErr = !id.trim() ? (activeRole === 'organization' ? 'Official business email is required' : activeRole === 'admin' ? 'Admin ID or official email is required' : 'Officer ID is required') : null;
      const pwErr = !password ? 'Password is required' : null;
      setErrors({ id: idErr, password: pwErr });
      if (idErr || pwErr) return;
      if (!captchaOk) {
        showToast('error', 'Please complete the CAPTCHA.');
        return;
      }
      setSubmitting(true);
      void authenticate(id.trim(), password, activeRole as Role, activeRole === 'organization' ? otp.trim() || undefined : undefined).finally(() => setSubmitting(false));
    },
    [activeRole, id, password, otp, captchaOk, authenticate, showToast]
  );

  const idLabel = activeRole === 'organization' ? 'Official Business Email' : activeRole === 'admin' ? 'Admin ID / Official Email' : 'Officer ID';
  const idPlaceholder = activeRole === 'organization' ? 'name@organization.in' : activeRole === 'admin' ? 'Admin ID or official email' : 'Officer ID';
  const title = activeRole === 'organization' ? 'Organization Sign In' : activeRole === 'admin' ? 'Admin Sign In' : 'Officer Sign In';

  return (
    <AuthShell brandSide={<BrandPanel title="Verify packaged commodity compliance with confidence." subtitle="NIRIKSHA connects organizations and Legal Metrology teams through secure, evidence-based compliance workflows." features={[{ icon: <ScanLine className="w-4 h-4 text-white" />, text: 'AI-powered label scanning & compliance checks' }, { icon: <FileCheck className="w-4 h-4 text-white" />, text: 'Persistent compliance findings and reports' }, { icon: <MapPin className="w-4 h-4 text-white" />, text: 'Jurisdiction-aware administrative oversight' }]} />}>
      <div className="lg:hidden flex items-center gap-2.5 mb-6"><div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center"><ShieldCheck className="w-5 h-5 text-white" /></div><div><p className="font-display font-extrabold text-ink-900 text-lg leading-none">NIRIKSHA</p><p className="text-[11px] text-ink-500 mt-1 leading-none">AI-Powered Product Compliance</p></div></div>
      <Breadcrumbs items={[{ label: 'Home' }, { label: title, active: true }]} />
      {!fixedRole && <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-ink-100 mb-6">{roleOptions.map(({ key, label, icon: Icon }) => <button key={key} type="button" onClick={() => { setRole(key); setId(''); setPassword(''); setOtp(''); setErrors({}); }} className={`flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${role === key ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500'}`}><Icon className="w-4 h-4" />{label}</button>)}</div>}
      <h1 className="text-2xl font-bold text-ink-900">{title}</h1>
      <p className="text-ink-500 mt-1 text-sm">{activeRole === 'organization' ? 'Access your organization compliance workspace.' : activeRole === 'admin' ? 'Access the administrative complaint and jurisdiction panel.' : 'Access your officer inspection workspace.'}</p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div><label className="label">{idLabel}</label><input className={`input ${errors.id ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`} value={id} onChange={(e) => setId(e.target.value)} placeholder={idPlaceholder} autoComplete="username" inputMode={activeRole === 'organization' ? 'email' : 'text'} />{errors.id && <p className="text-xs text-danger-600 mt-1">{errors.id}</p>}</div>
        <PasswordField label="Password" value={password} onChange={setPassword} error={errors.password} placeholder="Enter your password" autoComplete="current-password" />
        {activeRole === 'organization' && <div><label className="label flex items-center gap-1.5"><KeyRound className="w-3.5 h-3.5" /> OTP</label><input className="input" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 8))} placeholder="Enter OTP if required by your organization" inputMode="numeric" autoComplete="one-time-code" /><p className="text-xs text-ink-400 mt-1">OTP verification is used when enabled by the backend provider.</p></div>}
        <Captcha onVerify={setCaptchaOk} />
        <div className="flex items-center justify-between text-sm"><label className="flex items-center gap-2 cursor-pointer text-ink-600"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="rounded border-ink-300 text-brand-600 focus:ring-brand-500" />Remember me</label><button type="button" className="text-brand-600 font-medium hover:text-brand-700">Forgot Password?</button></div>
        <button type="submit" disabled={submitting} className="btn-primary w-full py-3"><LogIn className="w-4 h-4" />{submitting ? 'Signing in…' : 'Sign In'}</button>
      </form>
      {activeRole !== 'admin' && <p className="text-center text-sm text-ink-500 mt-6">Need an account? <button onClick={() => navigate(activeRole === 'organization' ? 'signup-organization' : 'signup-officer')} className="text-brand-600 font-semibold hover:text-brand-700">Register as {activeRole === 'organization' ? 'Organization' : 'Officer'}</button></p>}
      {activeRole === 'organization' && <button onClick={() => navigate('admin-login')} className="btn-ghost text-ink-500 text-sm mt-3 w-full justify-center">Admin sign in</button>}
      {activeRole === 'admin' && <button onClick={() => navigate('login')} className="btn-ghost text-ink-500 text-sm mt-3 w-full justify-center">Organization / Officer sign in</button>}
    </AuthShell>
  );
}
