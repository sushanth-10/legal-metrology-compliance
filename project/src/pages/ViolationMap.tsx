import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, MapPin } from 'lucide-react';
import { PageHeader, EmptyState } from '@/components/ui';
import { apiJson } from '@/lib/api';
import { useApp } from '@/store';

type ViolationRow = { state: string; district: string; rule_id: string; count: number };
export function ViolationMap() {
  const { showToast } = useApp();
  const [rows, setRows] = useState<ViolationRow[]>([]);
  const [state, setState] = useState('');
  const [district, setDistrict] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => { setLoading(true); const params = new URLSearchParams(); if (state) params.set('state', state); if (district) params.set('district', district); void apiJson<ViolationRow[]>(`/api/admin/violations${params.toString() ? `?${params}` : ''}`).then(setRows).catch((error) => showToast('error', error instanceof Error ? error.message : 'Violation data could not be loaded.')).finally(() => setLoading(false)); }, [state, district, showToast]);
  const states = useMemo(() => [...new Set(rows.map((row) => row.state))], [rows]);
  const districts = useMemo(() => [...new Set(rows.filter((row) => !state || row.state === state).map((row) => row.district))], [rows, state]);
  const total = rows.reduce((sum, row) => sum + Number(row.count), 0);
  return <div><PageHeader title="Violation Map" subtitle="Jurisdiction monitoring based on persisted compliance findings. Locations without database geography are shown as not provided." /><section className="card p-4 mb-5"><div className="grid md:grid-cols-2 gap-3"><select className="input" value={state} onChange={(e) => { setState(e.target.value); setDistrict(''); }}><option value="">All states</option>{states.map((item) => <option key={item}>{item}</option>)}</select><select className="input" value={district} onChange={(e) => setDistrict(e.target.value)}><option value="">All districts</option>{districts.map((item) => <option key={item}>{item}</option>)}</select></div></section><div className="grid sm:grid-cols-3 gap-4 mb-5"><div className="card p-5"><AlertTriangle className="w-5 h-5 text-danger-600" /><p className="text-2xl font-bold mt-2">{total}</p><p className="text-sm text-ink-500">Recorded violations</p></div><div className="card p-5"><MapPin className="w-5 h-5 text-brand-600" /><p className="text-2xl font-bold mt-2">{new Set(rows.map((row) => `${row.state}|${row.district}`)).size}</p><p className="text-sm text-ink-500">Affected locations</p></div></div>{loading ? <div className="card p-10 text-center text-ink-500"><Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />Loading persisted findings…</div> : rows.length === 0 ? <EmptyState icon={<MapPin className="w-5 h-5" />} title="No violation locations found" description="There are no recorded violation findings in the selected jurisdiction." /> : <div className="card overflow-hidden"><div className="overflow-x-auto"><table className="w-full"><thead className="bg-ink-50"><tr><th className="table-th">State</th><th className="table-th">District</th><th className="table-th">Rule ID</th><th className="table-th text-right">Violations</th></tr></thead><tbody className="divide-y divide-ink-100">{rows.map((row, index) => <tr key={`${row.state}-${row.district}-${row.rule_id}-${index}`}><td className="table-td">{row.state}</td><td className="table-td">{row.district}</td><td className="table-td font-medium">{row.rule_id}</td><td className="table-td text-right font-semibold text-danger-600">{row.count}</td></tr>)}</tbody></table></div></div>}</div>;
}
