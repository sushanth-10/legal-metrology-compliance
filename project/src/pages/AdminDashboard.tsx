import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock3, Eye, FileWarning, Loader2, Search, ShieldCheck, XCircle } from 'lucide-react';
import { useApp } from '@/store';
import { apiJson } from '@/lib/api';
import { EmptyState, PageHeader } from '@/components/ui';
import type { Complaint, ComplaintStatus } from '@/types';

type AdminStats = { total_complaints: number; new: number; under_review: number; investigating: number; resolved: number; requires_attention: number };
type AdminFilters = { states: string[]; districts: string[]; categories: string[] };

const statusLabel: Record<string, string> = { new: 'New', review: 'Under Review', investigating: 'Investigating', resolved: 'Resolved', closed: 'Closed' };
const statusClass: Record<string, string> = { new: 'bg-brand-50 text-brand-700', review: 'bg-warning-50 text-warning-700', investigating: 'bg-purple-50 text-purple-700', resolved: 'bg-success-50 text-success-700', closed: 'bg-ink-100 text-ink-700' };

function formatDate(value?: string) { return value ? new Date(value).toLocaleString() : '—'; }

export function AdminDashboard({ initialSection }: { initialSection?: 'complaints' } = {}) {
  const { user, complaintsLoading, updateComplaintStatus, showToast } = useApp();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [filters, setFilters] = useState<AdminFilters>({ states: [], districts: [], categories: [] });
  const [rows, setRows] = useState<Complaint[]>([]);
  const [selected, setSelected] = useState<Complaint | null>(null);
  const [query, setQuery] = useState({ search: '', state: '', district: '', status: '', category: '', date: '' });
  const [remark, setRemark] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams(Object.entries(query).filter(([, value]) => value));
      const [nextStats, nextRows] = await Promise.all([
        apiJson<AdminStats>(`/api/admin/dashboard${query.state || query.district ? `?${new URLSearchParams({ ...(query.state ? { state: query.state } : {}), ...(query.district ? { district: query.district } : {}) })}` : ''}`),
        apiJson<Complaint[]>(`/api/admin/complaints${params.toString() ? `?${params}` : ''}`),
      ]);
      setStats(nextStats); setRows(nextRows); setSelected((current) => current ? nextRows.find((item) => item.id === current.id) || current : null);
    } catch (error) { showToast('error', error instanceof Error ? error.message : 'Admin data could not be loaded.'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void Promise.all([apiJson<AdminFilters>('/api/admin/filters').then(setFilters), load()]); }, []);
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 250); return () => window.clearTimeout(timer); }, [query.search, query.state, query.district, query.status, query.category, query.date]);

  const open = async (complaint: Complaint) => {
    try { const detail = await apiJson<Complaint>(`/api/complaints/${encodeURIComponent(complaint.id)}`); setSelected(detail); setRemark(detail.adminRemark || ''); }
    catch (error) { showToast('error', error instanceof Error ? error.message : 'Complaint details could not be loaded.'); }
  };
  const update = async (status: ComplaintStatus) => {
    if (!selected) return;
    await updateComplaintStatus(selected.id, status, remark);
    await load();
    try { setSelected(await apiJson<Complaint>(`/api/complaints/${encodeURIComponent(selected.id)}`)); } catch { /* list remains authoritative */ }
    showToast('success', 'Complaint status saved to the database.');
  };

  const statCards = stats ? [
    ['Total Complaints', stats.total_complaints, FileWarning, 'text-brand-600'], ['New', stats.new, AlertCircle, 'text-brand-600'], ['Under Review', stats.under_review, Clock3, 'text-warning-600'], ['Investigating', stats.investigating, Search, 'text-purple-600'], ['Resolved', stats.resolved, CheckCircle2, 'text-success-600'], ['Requires Attention', stats.requires_attention, XCircle, 'text-danger-600'],
  ] as const : [];

  return <div>
    <PageHeader title="Admin Panel" subtitle={`Administrative oversight for ${user.state || 'all available'}${user.district ? ` • ${user.district}` : ''}.`} />
    <div className="grid grid-cols-2 xl:grid-cols-6 gap-3 mb-6">{statCards.map(([label, value, Icon, color]) => <div className="card p-4" key={label}><Icon className={`w-5 h-5 ${color}`} /><p className="text-2xl font-bold text-ink-900 mt-2">{value}</p><p className="text-xs text-ink-500 mt-1">{label}</p></div>)}</div>
    {initialSection && <div className="mb-4 text-sm font-semibold text-brand-700 flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> Complaint management</div>}
    <section className="card p-4 mb-5"><div className="grid md:grid-cols-3 xl:grid-cols-6 gap-3">
      <input className="input" placeholder="Search complaints" value={query.search} onChange={(e) => setQuery({ ...query, search: e.target.value })} />
      <select className="input" value={query.state} onChange={(e) => setQuery({ ...query, state: e.target.value, district: '' })}><option value="">All states</option>{filters.states.map((item) => <option key={item}>{item}</option>)}</select>
      <select className="input" value={query.district} onChange={(e) => setQuery({ ...query, district: e.target.value })}><option value="">All districts</option>{filters.districts.map((item) => <option key={item}>{item}</option>)}</select>
      <select className="input" value={query.status} onChange={(e) => setQuery({ ...query, status: e.target.value })}><option value="">All statuses</option>{Object.entries(statusLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      <select className="input" value={query.category} onChange={(e) => setQuery({ ...query, category: e.target.value })}><option value="">All categories</option>{filters.categories.map((item) => <option key={item}>{item}</option>)}</select>
      <input className="input" type="date" value={query.date} onChange={(e) => setQuery({ ...query, date: e.target.value })} />
    </div></section>
    <section className="card overflow-hidden"><div className="overflow-x-auto"><table className="w-full"><thead className="bg-ink-50"><tr>{['Complaint', 'Submitted', 'Product / Organization', 'Location', 'Category', 'Status', 'Action'].map((heading) => <th className="table-th" key={heading}>{heading}</th>)}</tr></thead><tbody className="divide-y divide-ink-100">
      {loading || complaintsLoading ? <tr><td colSpan={7} className="p-10 text-center text-ink-500"><Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />Loading database records…</td></tr> : rows.length === 0 ? <tr><td colSpan={7}><EmptyState icon={<FileWarning className="w-5 h-5" />} title="No complaints found" description="There are no database records matching these filters in your permitted jurisdiction." /></td></tr> : rows.map((item) => <tr key={item.id} className="hover:bg-ink-50/60"><td className="table-td font-medium">{item.id}</td><td className="table-td text-xs text-ink-500">{formatDate(item.date)}</td><td className="table-td"><div className="font-medium">{item.product}</div><div className="text-xs text-ink-500 mt-1">{item.organizationName || item.submittedBy || '—'}</div></td><td className="table-td">{item.location}<div className="text-xs text-ink-500">{[item.district, item.state].filter(Boolean).join(', ')}</div></td><td className="table-td">{item.category}</td><td className="table-td"><span className={`badge ${statusClass[item.status] || 'bg-ink-100 text-ink-700'}`}>{statusLabel[item.status] || item.status}</span></td><td className="table-td"><button onClick={() => void open(item)} className="btn-secondary px-3 py-1.5 text-xs"><Eye className="w-3.5 h-3.5" />Review</button></td></tr>)}</tbody></table></div></section>
    {selected && <div className="fixed inset-0 z-50 bg-ink-950/60 flex items-center justify-center p-4"><div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white border border-ink-200 shadow-2xl p-5"><div className="flex justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-ink-500">Complaint review</p><h2 className="text-xl font-bold text-ink-900 mt-1">{selected.id} · {selected.product}</h2></div><button className="btn-secondary" onClick={() => setSelected(null)}>Close</button></div><div className="grid md:grid-cols-2 gap-4 mt-5 text-sm"><div><b>Organization:</b> {selected.organizationName || selected.submittedBy || '—'}</div><div><b>Category:</b> {selected.category}</div><div><b>Location:</b> {selected.location}</div><div><b>Submitted:</b> {formatDate(selected.date)}</div><div className="md:col-span-2"><b>Description:</b><p className="mt-1 whitespace-pre-wrap text-ink-600">{selected.description || 'No description provided.'}</p></div></div>{selected.evidenceImages?.length ? <div className="mt-5"><h3 className="font-semibold">Evidence</h3><div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">{selected.evidenceImages.map((image, index) => <img key={`${image}-${index}`} src={image} alt={`Evidence ${index + 1}`} className="w-full aspect-square object-cover rounded-lg border border-ink-200" />)}</div></div> : null}<div className="mt-5 rounded-xl bg-ink-50 border border-ink-200 p-4"><h3 className="font-semibold">Database status</h3><select className="input mt-3" value={selected.status} onChange={(e) => setSelected({ ...selected, status: e.target.value as ComplaintStatus })}>{Object.entries(statusLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><textarea className="input mt-3 min-h-24" placeholder="Administrative remark" value={remark} onChange={(e) => setRemark(e.target.value)} /><button className="btn-primary mt-3" onClick={() => void update(selected.status)}>Save status and remark</button></div>{selected.history?.length ? <div className="mt-5"><h3 className="font-semibold">Status history</h3><div className="mt-2 space-y-2">{selected.history.map((event) => <div key={event.id} className="text-sm border-l-2 border-brand-300 pl-3"><b>{statusLabel[event.newStatus.toLowerCase()] || event.newStatus}</b> · {formatDate(event.changedAt)}<div className="text-ink-500">{event.changedBy || 'System'}{event.administrativeRemark ? ` — ${event.administrativeRemark}` : ''}</div></div>)}</div></div> : null}</div></div>}
  </div>;
}
