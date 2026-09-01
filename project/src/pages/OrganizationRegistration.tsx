import { useState } from 'react';
import { ArrowLeft, ArrowRight, Building2, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { useApp } from '@/store';
import { AuthShell, BrandPanel, Breadcrumbs, FieldError, PasswordField } from '@/components/Auth';
import { validateConfirmPassword, validateEmail, validateMobile, validatePassword, validateRequired } from '@/lib/validation';
import type { OrganizationRegistration as OrganizationRegistrationData } from '@/types';

const organizationTypes = ['Manufacturer', 'Packer', 'Importer', 'Distributor', 'Retailer', 'Other'];

export function OrganizationRegistration() {
  const { navigate, registerOrganization, showToast } = useApp();
  const [form, setForm] = useState<OrganizationRegistrationData>({ organizationName: '', organizationType: organizationTypes[0], officialEmail: '', officialMobile: '', registeredAddress: '', state: '', district: '', pinCode: '', gstin: '', registrationNumber: '', representativeName: '', representativeDesignation: '', representativeContact: '', password: '', confirmPassword: '', website: '', industry: '' });
  const [errors, setErrors] = useState<Partial<Record<keyof OrganizationRegistrationData, string | null>>>({});
  const [submitting, setSubmitting] = useState(false);

  const set = <K extends keyof OrganizationRegistrationData>(key: K, value: OrganizationRegistrationData[K]) => {
    setForm((previous) => ({ ...previous, [key]: value }));
    setErrors((previous) => ({ ...previous, [key]: null }));
  };

  const validate = () => {
    const next: Partial<Record<keyof OrganizationRegistrationData, string | null>> = {
      organizationName: validateRequired(form.organizationName, 'Organization / Company Name'),
      organizationType: validateRequired(form.organizationType, 'Organization Type'),
      officialEmail: validateEmail(form.officialEmail),
      officialMobile: validateMobile(form.officialMobile),
      registeredAddress: validateRequired(form.registeredAddress, 'Registered Business Address'),
      state: validateRequired(form.state, 'State'),
      district: validateRequired(form.district, 'District'),
      pinCode: /^\d{6}$/.test(form.pinCode) ? null : 'Enter a valid 6-digit PIN Code',
      gstin: validateRequired(form.gstin, 'GSTIN'),
      registrationNumber: validateRequired(form.registrationNumber, 'Business Registration Number'),
      representativeName: validateRequired(form.representativeName, 'Authorized Representative Name'),
      representativeDesignation: validateRequired(form.representativeDesignation, 'Authorized Representative Designation'),
      representativeContact: validateMobile(form.representativeContact),
      password: validatePassword(form.password),
      confirmPassword: validateConfirmPassword(form.confirmPassword, form.password),
    };
    setErrors(next);
    return !Object.values(next).some(Boolean);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) { showToast('error', 'Please fix the errors in the organization registration form.'); return; }
    setSubmitting(true);
    void registerOrganization(form).finally(() => setSubmitting(false));
  };

  const textField = (key: keyof OrganizationRegistrationData, label: string, placeholder: string, type = 'text') => (
    <div><label className="label">{label}</label><input type={type} className={`input ${errors[key] ? 'border-danger-300' : ''}`} value={String(form[key] || '')} onChange={(event) => set(key, event.target.value)} placeholder={placeholder} /> <FieldError error={errors[key]} /></div>
  );

  return (
    <AuthShell brandSide={<BrandPanel title="Create your organization compliance workspace." subtitle="Register the business entity responsible for manufacturing, packing, importing, distributing, or retailing packaged products." features={[{ icon: <Building2 className="w-4 h-4 text-white" />, text: 'Entity-based compliance records' }, { icon: <CheckCircle2 className="w-4 h-4 text-white" />, text: 'Persistent scans, evidence, and reports' }, { icon: <ShieldCheck className="w-4 h-4 text-white" />, text: 'Secure organization access' }]} />}>
      <Breadcrumbs items={[{ label: 'Home' }, { label: 'Organization Registration', active: true }]} />
      <div className="flex items-center gap-2.5 mb-1"><div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center"><Building2 className="w-5 h-5" /></div><h1 className="text-2xl font-bold text-ink-900">Organization Registration</h1></div>
      <p className="text-ink-500 text-sm">Create an account for your registered business entity.</p>

      <form onSubmit={submit} className="mt-6 space-y-6">
        <section><h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700 mb-3">Organization Details</h2><div className="space-y-4">{textField('organizationName', 'Organization / Company Name', 'Registered company name')}<div><label className="label">Organization Type</label><select className="input" value={form.organizationType} onChange={(event) => set('organizationType', event.target.value)}>{organizationTypes.map((type) => <option key={type}>{type}</option>)}</select><FieldError error={errors.organizationType} /></div><div className="grid sm:grid-cols-2 gap-4">{textField('officialEmail', 'Official Business Email', 'name@organization.in', 'email')}{textField('officialMobile', 'Official Mobile Number', '10-digit number', 'tel')}</div>{textField('registeredAddress', 'Registered Business Address', 'Full registered business address')}<div className="grid sm:grid-cols-3 gap-4">{textField('state', 'State', 'State')}{textField('district', 'District', 'District')}{textField('pinCode', 'PIN Code', '6-digit PIN', 'text')}</div></div></section>
        <section><h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700 mb-3">Business Identification</h2><div className="space-y-4">{textField('gstin', 'GSTIN', 'GST identification number')}{textField('registrationNumber', 'CIN / LLPIN / Business Registration Number', 'Registration number')}<div className="grid sm:grid-cols-2 gap-4">{textField('representativeName', 'Authorized Representative Name', 'Full name')}{textField('representativeDesignation', 'Authorized Representative Designation', 'Designation')}</div>{textField('representativeContact', 'Authorized Representative Contact Number', '10-digit number', 'tel')}</div></section>
        <section><h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700 mb-3">Account Security</h2><div className="grid sm:grid-cols-2 gap-4"><PasswordField label="Password" value={form.password} onChange={(value) => set('password', value)} error={errors.password} placeholder="Min. 8 characters" autoComplete="new-password" /><PasswordField label="Confirm Password" value={form.confirmPassword} onChange={(value) => set('confirmPassword', value)} error={errors.confirmPassword} placeholder="Re-enter password" autoComplete="new-password" /></div></section>
        <section><h2 className="text-sm font-semibold uppercase tracking-wide text-brand-700 mb-3">Optional Information</h2><div className="grid sm:grid-cols-2 gap-4">{textField('website', 'Website', 'https://your-organization.in', 'url')}{textField('industry', 'Industry / Product Category', 'Food, cosmetics, household goods, etc.')}</div></section>
        <button type="submit" disabled={submitting} className="btn-primary w-full py-3"><ArrowRight className="w-4 h-4" />{submitting ? 'Creating organization account…' : 'Create Organization Account'}</button>
      </form>
      <p className="text-center text-sm text-ink-500 mt-6">Already have an account? <button onClick={() => navigate('login')} className="text-brand-600 font-semibold hover:text-brand-700">Sign In</button></p>
      <button onClick={() => navigate('signup')} className="btn-ghost text-ink-500 text-sm mt-2 w-full justify-center"><ArrowLeft className="w-4 h-4" /> Back to account selection</button>
    </AuthShell>
  );
}
