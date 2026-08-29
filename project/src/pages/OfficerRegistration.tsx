import { useState, useCallback } from 'react';
import {
  ShieldCheck,
  BadgeCheck,
  ArrowLeft,
  ArrowRight,
  Upload,
  FileText,
  CheckCircle2,
  Loader2,
  Clock,
  X,
} from 'lucide-react';
import { useApp } from '@/store';
import { AuthShell, BrandPanel, Breadcrumbs, PasswordField, FieldError } from '@/components/Auth';
import {
  validateRequired,
  validateEmail,
  validateMobile,
  validateOfficerId,
  validatePassword,
  validateConfirmPassword,
  validateFile,
} from '@/lib/validation';

interface FormData {
  fullName: string;
  officerId: string;
  department: string;
  designation: string;
  officialEmail: string;
  mobile: string;
  address: string;
  password: string;
  confirmPassword: string;
}

interface DocSlot {
  key: string;
  label: string;
  file: File | null;
  error: string | null;
}

const docSlots: { key: string; label: string }[] = [
  { key: 'govId', label: 'Government / Department ID proof' },
  { key: 'authorization', label: 'Official authorization document' },
  { key: 'identity', label: 'Supporting identity document' },
];

export function OfficerRegistration() {
  const { navigate, showToast } = useApp();
  const [form, setForm] = useState<FormData>({
    fullName: '',
    officerId: '',
    department: '',
    designation: '',
    officialEmail: '',
    mobile: '',
    address: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string | null>>>({});
  const [docs, setDocs] = useState<DocSlot[]>(
    docSlots.map((d) => ({ ...d, file: null, error: null }))
  );
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const set = (k: keyof FormData, v: string) => {
    setForm((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: null }));
  };

  const onFile = useCallback((key: string, file: File | undefined) => {
    if (!file) return;
    const err = validateFile(file);
    setDocs((prev) =>
      prev.map((d) => (d.key === key ? { ...d, file: err ? null : file, error: err } : d))
    );
  }, []);

  const removeFile = (key: string) => {
    setDocs((prev) => prev.map((d) => (d.key === key ? { ...d, file: null, error: null } : d)));
  };

  const validate = (): boolean => {
    const e: Partial<Record<keyof FormData, string | null>> = {};
    e.fullName = validateRequired(form.fullName, 'Full name');
    e.officerId = validateOfficerId(form.officerId);
    e.department = validateRequired(form.department, 'Department');
    e.designation = validateRequired(form.designation, 'Designation');
    e.officialEmail = validateEmail(form.officialEmail);
    e.mobile = validateMobile(form.mobile);
    e.address = validateRequired(form.address, 'Office address');
    e.password = validatePassword(form.password);
    e.confirmPassword = validateConfirmPassword(form.confirmPassword, form.password);
    setErrors(e);

    let docErrors = false;
    setDocs((prev) => {
      const next = prev.map((d) => {
        if (!d.file) {
          docErrors = true;
          return { ...d, error: 'This document is required' };
        }
        return d;
      });
      return next;
    });

    return !Object.values(e).some(Boolean) && !docErrors && confirmed;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmed) {
      showToast('error', 'Please confirm the accuracy of your information.');
      return;
    }
    if (!validate()) {
      showToast('error', 'Please fix the errors and upload all required documents.');
      return;
    }
    setSubmitting(true);
    setTimeout(() => {
      setSubmitting(false);
      setSubmitted(true);
      showToast('success', 'Registration submitted for verification.');
    }, 1000);
  };

  if (submitted) {
    return (
      <AuthShell
        brandSide={
          <BrandPanel
            title="Registration received."
            subtitle="Your officer registration is now pending verification by the department."
            features={[
              { icon: <Clock className="w-4 h-4 text-white" />, text: 'Verification typically takes 2-3 business days' },
              { icon: <CheckCircle2 className="w-4 h-4 text-white" />, text: 'You will be notified once approved' },
              { icon: <ShieldCheck className="w-4 h-4 text-white" />, text: 'Officer access is granted only after verification' },
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

        <Breadcrumbs items={[{ label: 'Home' }, { label: 'Sign Up' }, { label: 'Officer Registration', active: true }]} />

        <div className="text-center py-6">
          <div className="w-16 h-16 rounded-2xl bg-success-50 text-success-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold text-ink-900 mt-4">Registration Submitted</h1>
          <span className="badge bg-warning-50 text-warning-700 mt-3">
            <Clock className="w-3.5 h-3.5" /> Pending Verification
          </span>
          <p className="text-ink-500 text-sm mt-4 max-w-sm mx-auto">
            Your officer registration has been submitted for verification. You will be able to
            access the officer dashboard after your credentials are verified.
          </p>
          <button onClick={() => navigate('login')} className="btn-primary mt-6 px-6 py-3">
            Back to Sign In
          </button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      brandSide={
        <BrandPanel
          title="Register as an authorized Legal Metrology officer."
          subtitle="Officer registration is restricted to authorized officials. All submissions are verified before access is granted."
          features={[
            { icon: <BadgeCheck className="w-4 h-4 text-white" />, text: 'Conduct field compliance inspections' },
            { icon: <FileText className="w-4 h-4 text-white" />, text: 'Generate official compliance reports' },
            { icon: <ShieldCheck className="w-4 h-4 text-white" />, text: 'Manage and resolve consumer complaints' },
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

      <Breadcrumbs items={[{ label: 'Home' }, { label: 'Sign Up' }, { label: 'Officer Registration', active: true }]} />

      <div className="flex items-center gap-2.5 mb-1">
        <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center">
          <BadgeCheck className="w-5 h-5" />
        </div>
        <h1 className="text-2xl font-bold text-ink-900">Officer Registration</h1>
      </div>
      <p className="text-ink-500 text-sm">Registration is restricted to authorized Legal Metrology officials.</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Full Name</label>
            <input
              className={`input ${errors.fullName ? 'border-danger-300' : ''}`}
              value={form.fullName}
              onChange={(e) => set('fullName', e.target.value)}
              placeholder="e.g. Inspector Meera Iyer"
            />
            <FieldError error={errors.fullName} />
          </div>
          <div>
            <label className="label">Officer ID</label>
            <input
              className={`input ${errors.officerId ? 'border-danger-300' : ''}`}
              value={form.officerId}
              onChange={(e) => set('officerId', e.target.value.toUpperCase())}
              placeholder="e.g. OFFICER001"
            />
            <FieldError error={errors.officerId} />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Department</label>
            <input
              className={`input ${errors.department ? 'border-danger-300' : ''}`}
              value={form.department}
              onChange={(e) => set('department', e.target.value)}
              placeholder="e.g. Legal Metrology, Karnataka"
            />
            <FieldError error={errors.department} />
          </div>
          <div>
            <label className="label">Designation</label>
            <input
              className={`input ${errors.designation ? 'border-danger-300' : ''}`}
              value={form.designation}
              onChange={(e) => set('designation', e.target.value)}
              placeholder="e.g. Inspector"
            />
            <FieldError error={errors.designation} />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Official Email</label>
            <input
              className={`input ${errors.officialEmail ? 'border-danger-300' : ''}`}
              value={form.officialEmail}
              onChange={(e) => set('officialEmail', e.target.value)}
              placeholder="name@gov.in"
              inputMode="email"
            />
            <FieldError error={errors.officialEmail} />
          </div>
          <div>
            <label className="label">Mobile Number</label>
            <input
              className={`input ${errors.mobile ? 'border-danger-300' : ''}`}
              value={form.mobile}
              onChange={(e) => set('mobile', e.target.value.replace(/\D/g, '').slice(0, 10))}
              placeholder="10-digit number"
              inputMode="numeric"
            />
            <FieldError error={errors.mobile} />
          </div>
        </div>

        <div>
          <label className="label">Office / Department Address</label>
          <textarea
            className={`input min-h-[72px] resize-y ${errors.address ? 'border-danger-300' : ''}`}
            value={form.address}
            onChange={(e) => set('address', e.target.value)}
            placeholder="Full office address"
          />
          <FieldError error={errors.address} />
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

        {/* Official verification */}
        <div className="rounded-xl border border-ink-200 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-brand-600" />
            <h3 className="font-semibold text-ink-900 text-sm">Official Verification</h3>
          </div>
          <p className="text-xs text-ink-500">
            Upload the following documents. Accepted formats: PDF, JPG, PNG | Maximum 5 MB.
          </p>

          <div className="space-y-3">
            {docs.map((d) => (
              <div key={d.key}>
                <label className="label">{d.label}</label>
                {d.file ? (
                  <div className="flex items-center gap-2 rounded-xl border border-success-200 bg-success-50 px-3.5 py-2.5">
                    <FileText className="w-4 h-4 text-success-600 shrink-0" />
                    <span className="text-sm text-ink-700 flex-1 truncate">{d.file.name}</span>
                    <span className="text-xs text-ink-500">{(d.file.size / 1024 / 1024).toFixed(1)} MB</span>
                    <button type="button" onClick={() => removeFile(d.key)} className="text-ink-400 hover:text-danger-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label className="flex items-center gap-2 rounded-xl border-2 border-dashed border-ink-300 hover:border-brand-400 hover:bg-brand-50/40 px-3.5 py-2.5 cursor-pointer transition-colors">
                    <Upload className="w-4 h-4 text-ink-400" />
                    <span className="text-sm text-ink-500">Tap to upload</span>
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      className="hidden"
                      onChange={(e) => onFile(d.key, e.target.files?.[0])}
                    />
                  </label>
                )}
                <FieldError error={d.error} />
              </div>
            ))}
          </div>
        </div>

        {/* Confirmation checkbox */}
        <label className="flex items-start gap-2.5 cursor-pointer text-sm text-ink-600">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="mt-0.5 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
          />
          <span>
            I confirm that the information provided is accurate and that I am an authorized officer.
          </span>
        </label>

        <button type="submit" disabled={submitting} className="btn-primary w-full py-3">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          {submitting ? 'Submitting…' : 'Submit for Verification'}
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
