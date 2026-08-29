import { useState } from 'react';
import {
  MessageSquareWarning,
  Upload,
  Send,
  MapPin,
  Store,
  Tag,
  FileText,
  ArrowLeft,
  Link2,
  Image as ImageIcon,
  CheckCircle2,
  Clock,
  Search as SearchIcon,
} from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader, EmptyState } from '@/components/ui';
import type { Complaint, ComplaintStatus } from '@/types';

const categories = [
  'MRP Discrepancy',
  'Missing Declarations',
  'Weight Discrepancy',
  'No MRP',
  'Tampered Label',
  'Other',
];

const statusConfig: Record<
  ComplaintStatus,
  { label: string; badge: string; dot: string }
> = {
  new: { label: 'New', badge: 'bg-brand-50 text-brand-700', dot: 'bg-brand-500' },
  review: { label: 'Under Review', badge: 'bg-warning-50 text-warning-700', dot: 'bg-warning-500' },
  investigating: { label: 'Investigating', badge: 'bg-warning-100 text-warning-800', dot: 'bg-warning-600' },
  resolved: { label: 'Resolved', badge: 'bg-success-50 text-success-700', dot: 'bg-success-500' },
};

const statusOrder: ComplaintStatus[] = ['new', 'review', 'investigating', 'resolved'];

export function Complaints() {
  const { role, complaints, addComplaint, updateComplaintStatus, user } = useApp();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<ComplaintStatus | 'all'>('all');

  if (role === 'consumer') {
    return showForm ? (
      <SubmitForm
        onBack={() => setShowForm(false)}
        onSubmit={(c) => {
          addComplaint(c);
          setShowForm(false);
        }}
        submittedBy={user.name}
      />
    ) : (
      <UserList
        complaints={complaints.filter((c) => c.submittedBy === user.name)}
        onSubmitNew={() => setShowForm(true)}
      />
    );
  }

  // Officer view
  const selected = complaints.find((c) => c.id === selectedId);
  const filtered = filter === 'all' ? complaints : complaints.filter((c) => c.status === filter);

  if (selected) {
    return <OfficerDetail complaint={selected} onBack={() => setSelectedId(null)} onUpdate={updateComplaintStatus} />;
  }

  return (
    <div>
      <PageHeader
        title="Complaint Management"
        subtitle="Review, investigate and resolve consumer complaints in your zone."
      />

      {/* Status summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statusOrder.map((s) => {
          const count = complaints.filter((c) => c.status === s).length;
          const cfg = statusConfig[s];
          return (
            <button
              key={s}
              onClick={() => setFilter(filter === s ? 'all' : s)}
              className={`card card-hover p-4 text-left ${filter === s ? 'ring-2 ring-brand-400' : ''}`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${cfg.dot}`} />
                <span className="text-xs font-semibold text-ink-500 uppercase tracking-wide">
                  {cfg.label}
                </span>
              </div>
              <p className="text-2xl font-bold text-ink-900 mt-2">{count}</p>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-ink-500">
          Showing {filtered.length} of {complaints.length} complaints
        </p>
        {filter !== 'all' && (
          <button onClick={() => setFilter('all')} className="btn-ghost text-brand-600 text-sm">
            Clear filter
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<MessageSquareWarning className="w-6 h-6" />}
          title="No complaints in this category"
          description="When consumers submit complaints matching this status, they will appear here."
        />
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((c) => {
            const cfg = statusConfig[c.status];
            return (
              <button
                key={c.id}
                onClick={() => setSelectedId(c.id)}
                className="card card-hover p-4 text-left flex flex-col gap-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <img
                      src={c.image}
                      alt={c.product}
                      className="w-12 h-12 rounded-lg object-cover"
                    />
                    <div>
                      <p className="font-semibold text-ink-800">{c.product}</p>
                      <p className="text-xs text-ink-500">{c.id}</p>
                    </div>
                  </div>
                  <span className={`badge ${cfg.badge}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                    {cfg.label}
                  </span>
                </div>
                <div className="space-y-1 text-sm text-ink-600">
                  <p className="flex items-center gap-1.5">
                    <Store className="w-3.5 h-3.5 text-ink-400" /> {c.shop}
                  </p>
                  <p className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-ink-400" /> {c.location}
                  </p>
                  <p className="flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-ink-400" /> {c.category}
                  </p>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-ink-100 text-xs text-ink-500">
                  <span>by {c.submittedBy}</span>
                  <span>{c.date}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function UserList({
  complaints,
  onSubmitNew,
}: {
  complaints: Complaint[];
  onSubmitNew: () => void;
}) {
  return (
    <div>
      <PageHeader
        title="Complaints"
        subtitle="Track the complaints you have submitted."
        actions={
          <button onClick={onSubmitNew} className="btn-primary">
            <MessageSquareWarning className="w-4 h-4" /> Submit a Complaint
          </button>
        }
      />

      {complaints.length === 0 ? (
        <EmptyState
          icon={<MessageSquareWarning className="w-6 h-6" />}
          title="No complaints yet"
          description="If you spot a non-compliant product, submit a complaint and an officer will review it."
        />
      ) : (
        <div className="space-y-3">
          {complaints.map((c) => {
            const cfg = statusConfig[c.status];
            return (
              <div key={c.id} className="card p-4 flex gap-3">
                <img src={c.image} alt={c.product} className="w-14 h-14 rounded-lg object-cover" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold text-ink-800">{c.product}</p>
                    <span className={`badge ${cfg.badge}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                      {cfg.label}
                    </span>
                  </div>
                  <p className="text-sm text-ink-500 mt-1">{c.category} • {c.shop}</p>
                  <p className="text-xs text-ink-400 mt-0.5">{c.date}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SubmitForm({
  onBack,
  onSubmit,
  submittedBy,
}: {
  onBack: () => void;
  onSubmit: (c: Complaint) => void;
  submittedBy: string;
}) {
  const [form, setForm] = useState({
    product: '',
    shop: '',
    location: '',
    category: categories[0],
    description: '',
  });
  const [image, setImage] = useState<string | null>(null);

  const valid = form.product && form.shop && form.location && form.description;

  const submit = () => {
    if (!valid) return;
    onSubmit({
      id: `cp-${Date.now()}`,
      product: form.product,
      image: image ?? 'https://images.pexels.com/photos/4467687/pexels-photo-4467687.jpeg?auto=compress&cs=tinysrgb&w=900',
      shop: form.shop,
      location: form.location,
      category: form.category,
      description: form.description,
      status: 'new',
      submittedBy,
      date: 'Just now',
      relatedScans: 0,
    });
  };

  return (
    <div className="max-w-2xl mx-auto">
      <button onClick={onBack} className="btn-ghost text-brand-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>
      <PageHeader title="Submit a Complaint" subtitle="Report a non-compliant packaged product." />

      <div className="card p-5 sm:p-6 space-y-5">
        <div>
          <label className="label">Product name</label>
          <input
            className="input"
            value={form.product}
            onChange={(e) => setForm({ ...form, product: e.target.value })}
            placeholder="e.g. XYZ Biscuits 200g"
          />
        </div>

        <div>
          <label className="label">Product image</label>
          <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-ink-300 rounded-xl p-6 cursor-pointer hover:border-brand-400 hover:bg-brand-50/40 transition-colors">
            <div className="w-10 h-10 rounded-lg bg-ink-100 flex items-center justify-center text-ink-400">
              {image ? <img src={image} alt="" className="w-full h-full object-cover rounded-lg" /> : <Upload className="w-5 h-5" />}
            </div>
            <span className="text-sm text-ink-500">Tap to upload a photo of the product</span>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                const r = new FileReader();
                r.onload = () => setImage(r.result as string);
                r.readAsDataURL(f);
              }}
            />
          </label>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Shop / seller</label>
            <input
              className="input"
              value={form.shop}
              onChange={(e) => setForm({ ...form, shop: e.target.value })}
              placeholder="e.g. Sharma General Store"
            />
          </div>
          <div>
            <label className="label">Location</label>
            <input
              className="input"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="e.g. Jaynagar, Bengaluru"
            />
          </div>
        </div>

        <div>
          <label className="label">Complaint category</label>
          <select
            className="input"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          >
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            className="input min-h-[100px] resize-y"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Describe the issue you observed…"
          />
        </div>

        <div>
          <label className="label">Supporting evidence (optional)</label>
          <label className="flex items-center gap-2 text-sm text-ink-500 border border-ink-200 rounded-xl px-3 py-2.5 cursor-pointer hover:bg-ink-50">
            <FileText className="w-4 h-4 text-ink-400" />
            <span>Attach receipts, photos or documents</span>
            <input type="file" multiple className="hidden" />
          </label>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={submit} disabled={!valid} className="btn-primary flex-1 py-3">
            <Send className="w-4 h-4" /> Submit Complaint
          </button>
          <button onClick={onBack} className="btn-secondary py-3">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function OfficerDetail({
  complaint,
  onBack,
  onUpdate,
}: {
  complaint: Complaint;
  onBack: () => void;
  onUpdate: (id: string, status: ComplaintStatus) => void;
}) {
  const cfg = statusConfig[complaint.status];
  return (
    <div className="max-w-4xl mx-auto">
      <button onClick={onBack} className="btn-ghost text-brand-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to complaints
      </button>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-5">
          <div className="card p-5">
            <div className="flex items-start gap-4">
              <img
                src={complaint.image}
                alt={complaint.product}
                className="w-20 h-20 rounded-xl object-cover"
              />
              <div className="flex-1">
                <h2 className="text-xl font-bold text-ink-900">{complaint.product}</h2>
                <p className="text-sm text-ink-500 mt-0.5">{complaint.id} • by {complaint.submittedBy}</p>
                <span className={`badge ${cfg.badge} mt-2`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                  {cfg.label}
                </span>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="font-semibold text-ink-900 mb-3">Complaint Description</h3>
            <p className="text-sm text-ink-700">{complaint.description}</p>
            <div className="grid sm:grid-cols-2 gap-3 mt-4">
              <div className="rounded-lg bg-ink-50 p-3 text-sm">
                <p className="text-xs font-semibold text-ink-500 uppercase mb-1">Shop / Seller</p>
                <p className="text-ink-700 flex items-center gap-1.5">
                  <Store className="w-3.5 h-3.5 text-ink-400" /> {complaint.shop}
                </p>
              </div>
              <div className="rounded-lg bg-ink-50 p-3 text-sm">
                <p className="text-xs font-semibold text-ink-500 uppercase mb-1">Location</p>
                <p className="text-ink-700 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-ink-400" /> {complaint.location}
                </p>
              </div>
              <div className="rounded-lg bg-ink-50 p-3 text-sm">
                <p className="text-xs font-semibold text-ink-500 uppercase mb-1">Category</p>
                <p className="text-ink-700 flex items-center gap-1.5">
                  <Tag className="w-3.5 h-3.5 text-ink-400" /> {complaint.category}
                </p>
              </div>
              <div className="rounded-lg bg-ink-50 p-3 text-sm">
                <p className="text-xs font-semibold text-ink-500 uppercase mb-1">Submitted</p>
                <p className="text-ink-700 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-ink-400" /> {complaint.date}
                </p>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="font-semibold text-ink-900 mb-3">Submitted Evidence</h3>
            <div className="grid grid-cols-3 gap-3">
              {[complaint.image, complaint.image, complaint.image].map((img, i) => (
                <div key={i} className="aspect-square rounded-lg overflow-hidden bg-ink-100">
                  <img src={img} alt="" className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          </div>

          {complaint.relatedScans ? (
            <div className="card p-5">
              <h3 className="font-semibold text-ink-900 mb-3 flex items-center gap-2">
                <Link2 className="w-4 h-4 text-brand-600" /> Related Scans
              </h3>
              <p className="text-sm text-ink-500">
                {complaint.relatedScans} related compliance scan{complaint.relatedScans > 1 ? 's' : ''} found for this product.
              </p>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <div className="card p-5">
            <h3 className="font-semibold text-ink-900 mb-3">Update Status</h3>
            <div className="space-y-2">
              {statusOrder.map((s) => {
                const sc = statusConfig[s];
                const active = complaint.status === s;
                return (
                  <button
                    key={s}
                    onClick={() => onUpdate(complaint.id, s)}
                    className={`w-full flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                      active ? 'bg-brand-50 text-brand-700' : 'text-ink-600 hover:bg-ink-50'
                    }`}
                  >
                    {active ? (
                      <CheckCircle2 className="w-4 h-4 text-brand-600" />
                    ) : (
                      <span className={`w-2.5 h-2.5 rounded-full ${sc.dot}`} />
                    )}
                    {sc.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="card p-5">
            <h3 className="font-semibold text-ink-900 mb-2">Officer Notes</h3>
            <textarea
              className="input min-h-[90px] resize-y"
              placeholder="Add investigation notes…"
            />
            <button className="btn-secondary w-full mt-3 justify-center">Save Note</button>
          </div>
        </div>
      </div>
    </div>
  );
}
