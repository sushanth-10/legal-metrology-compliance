import { useState, useCallback } from 'react';
import {
  ShieldCheck,
  User,
  ArrowLeft,
  ArrowRight,
  Send,
  CheckCircle2,
  Loader2,
  Fingerprint,
  Smartphone,
} from 'lucide-react';
import { useApp } from '@/store';
import { AuthShell, BrandPanel, Breadcrumbs, PasswordField, FieldError } from '@/components/Auth';
import {
  validateRequired,
  validateMobile,
  validateEmail,
  validateAadhaar,
  validateOtp,
  validatePassword,
  validateConfirmPassword,
  formatAadhaar,
  formatMobile,
} from '@/lib/validation';

interface FormData {
  fullName: string;
  mobile: string;
  email: string;
  aadhaar: string;
  password: string;
  confirmPassword: string;
}

export function ConsumerRegistration() {
  const { navigate, login, showToast } = useApp();
  const [form, setForm] = useState<FormData>({
    fullName: '',
    mobile: '',
    email: '',
    aadhaar: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string | null>>>({});
  const [aadhaarVerified, setAadhaarVerified] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState('');
  const [otpError, setOtpError] = useState<string | null>(null);
  const [sendingOtp, setSendingOtp] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const set = (k: keyof FormData, v: string) => {
    setForm((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: null }));
  };

  const sendOtp = useCallback(() => {
    const aErr = validateAadhaar(form.aadhaar);
    if (aErr) {
      setErrors((p) => ({ ...p, aadhaar: aErr }));
      return;
    }
    setSendingOtp(true);
    setTimeout(() => {
      setSendingOtp(false);
      setOtpSent(true);
      showToast('info', 'OTP sent to your registered mobile number. (Demo OTP: 123456)');
    }, 900);
  }, [form.aadhaar, showToast]);

  const verifyOtp = useCallback(() => {
    const oErr = validateOtp(otp);
    if (oErr) {
      setOtpError(oErr);
      return;
    }
    setVerifyingOtp(true);
    setTimeout(() => {
      setVerifyingOtp(false);
      if (otp === '123456') {
        setAadhaarVerified(true);
        setOtpError(null);
        showToast('success', 'Aadhaar verified successfully.');
      } else {
        setOtpError('Invalid OTP. Use 123456 for the demo.');
      }
    }, 800);
  }, [otp, showToast]);

  const validate = (): boolean => {
    const e: Partial<Record<keyof FormData, string | null>> = {};
    e.fullName = validateRequired(form.fullName, 'Full name');
    e.mobile = validateMobile(form.mobile);
    e.email = validateEmail(form.email);
    e.aadhaar = validateAadhaar(form.aadhaar);
    e.password = validatePassword(form.password);
    e.confirmPassword = validateConfirmPassword(form.confirmPassword, form.password);
    setErrors(e);
    return !Object.values(e).some(Boolean);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) {
      showToast('error', 'Please fix the errors in the form.');
      return;
    }
    if (!aadhaarVerified) {
      showToast('error', 'Please complete Aadhaar verification first.');
      return;
    }
    setSubmitting(true);
    setTimeout(() => {
      setSubmitting(false);
      showToast('success', 'Account created successfully!');
      login('consumer', form.fullName);
    }, 800);
  };

  return (
    <AuthShell
      brandSide={
        <BrandPanel
          title="Register as a consumer to verify products."
          subtitle="Create a consumer account to scan packaged products, check compliance, and report violations."
          features={[
            { icon: <Smartphone className="w-4 h-4 text-white" />, text: 'Scan product labels with your phone' },
            { icon: <Fingerprint className="w-4 h-4 text-white" />, text: 'Aadhaar-based identity verification' },
            { icon: <CheckCircle2 className="w-4 h-4 text-white" />, text: 'Report non-compliant products easily' },
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

      <Breadcrumbs items={[{ label: 'Home' }, { label: 'Sign Up' }, { label: 'Consumer Registration', active: true }]} />

      <div className="flex items-center gap-2.5 mb-1">
        <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center">
          <User className="w-5 h-5" />
        </div>
        <h1 className="text-2xl font-bold text-ink-900">Consumer Registration</h1>
      </div>
      <p className="text-ink-500 text-sm">Create your account to start scanning and verifying products.</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label className="label">Full Name</label>
          <input
            className={`input ${errors.fullName ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
            value={form.fullName}
            onChange={(e) => set('fullName', e.target.value)}
            placeholder="e.g. Aarav Sharma"
          />
          <FieldError error={errors.fullName} />
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Mobile Number</label>
            <input
              className={`input ${errors.mobile ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
              value={form.mobile}
              onChange={(e) => set('mobile', formatMobile(e.target.value))}
              placeholder="10-digit number"
              inputMode="numeric"
            />
            <FieldError error={errors.mobile} />
          </div>
          <div>
            <label className="label">Email Address</label>
            <input
              className={`input ${errors.email ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
              value={form.email}
              onChange={(e) => set('email', e.target.value)}
              placeholder="you@example.in"
              inputMode="email"
            />
            <FieldError error={errors.email} />
          </div>
        </div>

        {/* Aadhaar verification */}
        <div className="rounded-xl border border-ink-200 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Fingerprint className="w-4 h-4 text-brand-600" />
            <h3 className="font-semibold text-ink-900 text-sm">Verify Aadhaar</h3>
            {aadhaarVerified && (
              <span className="badge bg-success-50 text-success-700 ml-auto">
                <CheckCircle2 className="w-3.5 h-3.5" /> Aadhaar Verified
              </span>
            )}
          </div>
          <p className="text-xs text-ink-500">
            Aadhaar verification will be used for identity verification.
          </p>
          <div>
            <label className="label">Aadhaar Number</label>
            <input
              className={`input ${errors.aadhaar ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
              value={form.aadhaar}
              onChange={(e) => {
                set('aadhaar', formatAadhaar(e.target.value));
                setAadhaarVerified(false);
                setOtpSent(false);
                setOtp('');
              }}
              placeholder="XXXX XXXX XXXX"
              inputMode="numeric"
              disabled={aadhaarVerified}
            />
            <FieldError error={errors.aadhaar} />
          </div>

          {!aadhaarVerified && (
            <>
              {!otpSent ? (
                <button type="button" onClick={sendOtp} disabled={sendingOtp} className="btn-secondary w-full justify-center">
                  {sendingOtp ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  {sendingOtp ? 'Sending OTP…' : 'Send OTP'}
                </button>
              ) : (
                <div className="space-y-3 animate-fade-in">
                  <div>
                    <label className="label">Enter OTP</label>
                    <input
                      className={`input ${otpError ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-100' : ''}`}
                      value={otp}
                      onChange={(e) => {
                        setOtp(e.target.value.replace(/\D/g, '').slice(0, 6));
                        setOtpError(null);
                      }}
                      placeholder="6-digit OTP"
                      inputMode="numeric"
                    />
                    <FieldError error={otpError} />
                    <p className="text-xs text-ink-400 mt-1">Demo OTP: 123456</p>
                  </div>
                  <div className="flex gap-2">
                    <button type="button" onClick={verifyOtp} disabled={verifyingOtp} className="btn-primary flex-1 justify-center">
                      {verifyingOtp ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                      {verifyingOtp ? 'Verifying…' : 'Verify OTP'}
                    </button>
                    <button type="button" onClick={sendOtp} disabled={sendingOtp} className="btn-secondary">
                      Resend
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <PasswordField
            label="Password"
            value={form.password}
            onChange={(v) => set('password', v)}
            error={errors.password}
            placeholder="Min. 8 characters"
            autoComplete="new-password"
          />
          <PasswordField
            label="Confirm Password"
            value={form.confirmPassword}
            onChange={(v) => set('confirmPassword', v)}
            error={errors.confirmPassword}
            placeholder="Re-enter password"
            autoComplete="new-password"
          />
        </div>

        <button type="submit" disabled={submitting} className="btn-primary w-full py-3">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>
      </form>

      <p className="text-center text-sm text-ink-500 mt-6">
        Already have an account?{' '}
        <button onClick={() => navigate('login')} className="text-brand-600 font-semibold hover:text-brand-700">
          Sign In
        </button>
      </p>

      <button onClick={() => navigate('signup')} className="btn-ghost text-ink-500 text-sm mt-2 w-full justify-center">
        <ArrowLeft className="w-4 h-4" /> Back to account selection
      </button>
    </AuthShell>
  );
}
