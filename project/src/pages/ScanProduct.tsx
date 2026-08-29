import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { AlertCircle, ArrowLeft, Camera, CheckCircle2, ChevronDown, ChevronUp, Circle, CircleAlert, Eye, FileImage, FileText, ImageIcon, Info, Loader2, Plus, RotateCcw, ScanLine, SearchCheck, ShieldCheck, Sparkles, Upload, X } from 'lucide-react';
import { InfoNote, PageHeader } from '@/components/ui';

type Mode = 'report' | 'advanced';
type Stage = 'upload' | 'processing' | 'report' | 'advanced';
type Status = 'COMPLIANT' | 'VIOLATION' | 'UNABLE_TO_VERIFY' | 'NOT_APPLICABLE' | 'OFFICER_REVIEW_REQUIRED';
type Visibility = 'VISIBLE' | 'NOT_VISIBLE' | 'UNREADABLE' | 'NOT_ASSESSED';
type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'unable_to_verify';
type ImageItem = { id: string; name: string; url: string };
type ScanApiResponse = {
  overall_status: Status;
  checks: Check[];
  coverage?: { overall?: string; minimum_required_surfaces_covered?: boolean; notes?: string };
  summary?: { total_checks: number; compliant: number; violations: number; review: number };
};

/** Future Gemini/OCR contract: observations only; Python compliance_engine owns the legal decision. */
type ExtractedField = { value: string | null; visibility: Visibility; readable: boolean; confidence: number | null; sourceImage: number | null };
type ExtractedPackage = {
  product_name: ExtractedField; manufacturer_details: ExtractedField; packer_details: ExtractedField;
  importer_details: ExtractedField; country_of_origin: ExtractedField; net_quantity: ExtractedField;
  mrp: ExtractedField; unit_sale_price: ExtractedField; date_declaration: ExtractedField;
  best_before: ExtractedField; use_by: ExtractedField; consumer_care_details: ExtractedField; other_declarations: ExtractedField;
};
type Check = { id: keyof ExtractedPackage; label: string; status: Status; value: string; reference: string; explanation: string; sourceImage: number | null };
type Annotation = { id: string; x: number; y: number; w: number; h: number; status: Status; label: string };

const steps = ['Images uploaded', 'Image quality checked', 'Reading product label', 'Extracting product information', 'Checking mandatory declarations', 'Applying Legal Metrology rules', 'Generating compliance report'];
const mockChecks: Check[] = [
  { id: 'product_name', label: 'Product Name', status: 'COMPLIANT', value: 'Sample packaged commodity', reference: 'Rule 6(1)(b)', explanation: 'Example extracted declaration for the future result layout.', sourceImage: 0 },
  { id: 'manufacturer_details', label: 'Manufacturer Details', status: 'COMPLIANT', value: 'Example manufacturer, Bengaluru 560001', reference: 'Rule 6(1)(a)', explanation: 'Example name and address declaration.', sourceImage: 0 },
  { id: 'packer_details', label: 'Packer Details', status: 'UNABLE_TO_VERIFY', value: 'Not visible in supplied images', reference: 'Rule 6(1)(a)', explanation: 'Not a violation: a different package surface may contain it.', sourceImage: null },
  { id: 'importer_details', label: 'Importer Details', status: 'UNABLE_TO_VERIFY', value: 'Import status not established', reference: 'Rule 6(1)(a)', explanation: 'Applicability must be established first.', sourceImage: null },
  { id: 'country_of_origin', label: 'Country of Origin', status: 'UNABLE_TO_VERIFY', value: 'Import status not established', reference: 'Rule 6(1)(aa)', explanation: 'Applies to imported products only.', sourceImage: null },
  { id: 'net_quantity', label: 'Net Quantity', status: 'COMPLIANT', value: 'Net Qty: 200 g', reference: 'Rule 6(1)(c)', explanation: 'Example standard-unit declaration.', sourceImage: 0 },
  { id: 'mrp', label: 'MRP / Retail Sale Price', status: 'UNABLE_TO_VERIFY', value: 'Not visible in supplied images', reference: 'Rule 6(1)(e)', explanation: 'MRP was not visible in the uploaded images; it is not automatically missing.', sourceImage: null },
  { id: 'unit_sale_price', label: 'Unit Sale Price', status: 'UNABLE_TO_VERIFY', value: 'Applicability not classified', reference: 'Rule 6(11)', explanation: 'Assessed only where applicable.', sourceImage: null },
  { id: 'date_declaration', label: 'Date Declaration', status: 'COMPLIANT', value: 'Packed: Aug 2026', reference: 'Rule 6(1)(d)', explanation: 'Example month-and-year declaration.', sourceImage: 1 },
  { id: 'best_before', label: 'Best Before', status: 'UNABLE_TO_VERIFY', value: 'Product category not classified', reference: 'Rule 6(1)(da)', explanation: 'Applicability depends on commodity and other applicable law.', sourceImage: null },
  { id: 'use_by', label: 'Use By / Expiry', status: 'UNABLE_TO_VERIFY', value: 'Product category not classified', reference: 'Rule 6(1)(da)', explanation: 'Kept separate for future extraction.', sourceImage: null },
  { id: 'consumer_care_details', label: 'Consumer Care Details', status: 'VIOLATION', value: 'No complaint contact found on inspected label surface', reference: 'Rule 6(2)', explanation: 'Mock only: this example assumes the relevant surface was inspected.', sourceImage: 1 },
  { id: 'other_declarations', label: 'Other Applicable Declarations', status: 'UNABLE_TO_VERIFY', value: 'Awaiting product classification', reference: 'Rule 6 and related provisions', explanation: 'Special declarations are not universally mandatory.', sourceImage: null },
];
const annotations: Annotation[] = [
  { id: 'name', x: 12, y: 18, w: 47, h: 13, status: 'COMPLIANT', label: 'Product name' },
  { id: 'mrp', x: 56, y: 52, w: 30, h: 13, status: 'UNABLE_TO_VERIFY', label: 'MRP not visible' },
  { id: 'care', x: 10, y: 72, w: 74, h: 14, status: 'VIOLATION', label: 'Consumer care' },
];

function style(status: Status) {
  if (status === 'COMPLIANT') return { badge: 'bg-success-50 text-success-700', border: 'border-success-400', icon: CheckCircle2 };
  if (status === 'VIOLATION') return { badge: 'bg-danger-50 text-danger-700', border: 'border-danger-400', icon: CircleAlert };
  if (status === 'OFFICER_REVIEW_REQUIRED') return { badge: 'bg-brand-50 text-brand-700', border: 'border-brand-400', icon: ShieldCheck };
  if (status === 'NOT_APPLICABLE') return { badge: 'bg-ink-100 text-ink-700', border: 'border-ink-300', icon: Info };
  return { badge: 'bg-warning-50 text-warning-700', border: 'border-warning-400', icon: AlertCircle };
}
function Badge({ status }: { status: Status }) {
  const cfg = style(status); const Icon = cfg.icon;
  return <span className={'badge ' + cfg.badge}><Icon className="w-3.5 h-3.5" />{status.replace(/_/g, ' ')}</span>;
}

function ImageSlot({ image, index, choose, camera, drop, remove }: { image: ImageItem | null; index: number; choose: () => void; camera: () => void; drop: (e: DragEvent<HTMLDivElement>) => void; remove: () => void }) {
  return <div onDragOver={(e) => e.preventDefault()} onDrop={drop} className={'relative min-h-52 rounded-2xl border-2 border-dashed p-4 ' + (image ? 'border-ink-200 bg-ink-50' : 'border-ink-300 bg-white hover:border-brand-400 hover:bg-brand-50/30')}>
    {image ? <><img src={image.url} alt={'Uploaded label ' + (index + 1)} className="h-40 w-full rounded-xl object-cover bg-ink-100" /><div className="mt-3 flex gap-2 min-w-0"><FileImage className="w-4 h-4 text-brand-600 shrink-0" /><span className="text-sm font-medium text-ink-700 truncate">{image.name}</span></div><div className="mt-3 flex gap-2"><button onClick={choose} className="btn-secondary flex-1 py-2"><Upload className="w-3.5 h-3.5" />Replace</button><button aria-label={'Remove image ' + (index + 1)} onClick={remove} className="btn-secondary px-3 py-2 text-danger-600"><X className="w-4 h-4" /></button></div></> :
      <div className="min-h-48 flex flex-col items-center justify-center text-center"><div className="w-12 h-12 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><ImageIcon className="w-6 h-6" /></div><h3 className="font-semibold text-ink-800 mt-3">Label image {index + 1}</h3><p className="text-xs text-ink-500 mt-1 max-w-52">Upload a different package side for better coverage.</p><div className="mt-4 flex gap-2"><button onClick={choose} className="btn-secondary py-2"><Upload className="w-3.5 h-3.5" />Upload</button><button onClick={camera} className="btn-secondary py-2"><Camera className="w-3.5 h-3.5" />Photo</button></div></div>}
  </div>;
}

function Processing({ mode, results, back }: { mode: Mode; results: () => void; back: () => void }) {
  const [state] = useState<ProcessingStatus>('processing');
  return <div className="max-w-5xl mx-auto"><PageHeader title={mode === 'advanced' ? 'Advanced Scan in progress' : 'Generating compliance report'} subtitle="Ready for future backend processing events." /><div className="grid lg:grid-cols-[1.15fr_.85fr] gap-6"><section className="card p-5 sm:p-7"><div className="flex items-center gap-3 pb-5 border-b border-ink-100"><div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><ScanLine className="w-5 h-5" /></div><div><h2 className="font-semibold text-ink-900">Processing timeline</h2><p className="text-sm text-ink-500">No OCR or AI request is made in this demo.</p></div></div><ol className="mt-6">{steps.map((label, i) => <li key={label} className="flex gap-3 min-h-14"><div className="flex flex-col items-center">{i < 2 ? <CheckCircle2 className="w-5 h-5 text-success-500" /> : i === 2 ? <Loader2 className="w-5 h-5 text-brand-600 animate-spin" /> : <Circle className="w-5 h-5 text-ink-300" />}{i < steps.length - 1 && <div className={'w-px flex-1 my-1 ' + (i < 2 ? 'bg-success-200' : 'bg-ink-200')} />}</div><div className="pb-5"><p className={'text-sm font-medium ' + (i < 2 ? 'text-ink-800' : i === 2 ? 'text-brand-700' : 'text-ink-400')}>{label}</p>{i === 2 && <p className="text-xs text-ink-500 mt-0.5">Waiting for extractor events</p>}</div></li>)}</ol></section><aside className="space-y-4"><div className="card p-5"><span className="badge bg-brand-50 text-brand-700"><Loader2 className="w-3.5 h-3.5 animate-spin" />{state}</span><h2 className="font-semibold text-ink-900 mt-4">Future data flow</h2><p className="text-sm text-ink-600 mt-2 leading-6">Images → Gemini/OCR extraction → structured data → Python compliance_engine → results.</p><p className="text-sm text-ink-600 mt-2 leading-6">Gemini extracts only; Python rules determine compliance.</p></div><InfoNote>Mock results below demonstrate the interface only, not a finding about uploaded images.</InfoNote><button onClick={results} className="btn-primary w-full py-3"><FileText className="w-4 h-4" />View mock layout</button><button onClick={back} className="btn-secondary w-full py-3"><ArrowLeft className="w-4 h-4" />Back to images</button></aside></div></div>;
}

function CheckRow({ check, images }: { check: Check; images: Array<ImageItem | null> }) {
  const [open, setOpen] = useState(false); const [issue, setIssue] = useState<'missing' | 'no-label' | 'other' | null>(null); const [note, setNote] = useState(''); const [saved, setSaved] = useState(false);
  const source = check.sourceImage === null ? null : images[check.sourceImage];
  return <article className="border border-ink-200 rounded-xl overflow-hidden"><button onClick={() => setOpen(!open)} className="w-full text-left p-4 flex items-start gap-3 hover:bg-ink-50"><Badge status={check.status} /><div className="flex-1 min-w-0"><p className="font-semibold text-ink-900">{check.label}</p><p className="text-sm text-ink-500 mt-0.5 truncate">{check.value}</p></div>{open ? <ChevronUp className="w-4 h-4 text-ink-500 mt-1" /> : <ChevronDown className="w-4 h-4 text-ink-500 mt-1" />}</button>{open && <div className="border-t border-ink-100 p-4 bg-ink-50/50 grid md:grid-cols-[1fr_220px] gap-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Applicable requirement</p><p className="text-sm text-ink-700 mt-1">{check.reference}</p><p className="text-xs font-semibold uppercase tracking-wide text-ink-500 mt-4">Explanation</p><p className="text-sm text-ink-700 mt-1 leading-6">{check.explanation}</p>{check.id === 'mrp' && check.status === 'UNABLE_TO_VERIFY' && <div className="mt-4 rounded-xl border border-warning-200 bg-warning-50 p-3"><p className="text-sm font-semibold text-warning-800">Tell us what you observed</p><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => { setIssue('missing'); setSaved(false); }} className="btn-secondary py-2">MRP appears to be missing</button><button onClick={() => { setIssue('no-label'); setSaved(false); }} className="btn-secondary py-2">No label/declaration visible</button><button onClick={() => { setIssue('other'); setSaved(false); }} className="btn-secondary py-2">Other issue</button></div>{issue === 'other' && <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} className="input mt-3 resize-y" placeholder="Describe the issue for future review…" />}{issue && <button disabled={issue === 'other' && !note.trim()} onClick={() => setSaved(true)} className="btn-primary mt-3 py-2">Continue</button>}{saved && <p className="text-xs text-success-700 font-medium mt-3">Observation recorded for future review. Status is unchanged.</p>}</div>}</div><div><p className="text-xs font-semibold uppercase tracking-wide text-ink-500 mb-2">Evidence / source</p>{source ? <img src={source.url} alt={'Evidence for ' + check.label} className="w-full aspect-[4/3] object-cover rounded-lg border border-ink-200" /> : <div className="aspect-[4/3] rounded-lg border border-dashed border-ink-300 bg-white grid place-items-center p-3 text-center text-xs text-ink-500">No source image established</div>}</div></div>}</article>;
}

function Advanced({ images, back }: { images: Array<ImageItem | null>; back: () => void }) {
  const source = images.find(Boolean);
  return <div className="max-w-6xl mx-auto"><PageHeader title="Advanced scan findings" subtitle="Mock annotation layout — ready for backend evidence coordinates." actions={<button onClick={back} className="btn-secondary"><RotateCcw className="w-4 h-4" />Scan another product</button>} /><InfoNote>Advanced mode will combine extracted evidence and Python compliance_engine results. This sample does not analyse your images.</InfoNote><div className="grid xl:grid-cols-[1.05fr_.95fr] gap-6 mt-6"><section className="card p-4 sm:p-5"><div className="flex items-center justify-between mb-4"><h2 className="font-semibold text-ink-900">Annotated product image</h2><span className="badge bg-brand-50 text-brand-700"><Eye className="w-3.5 h-3.5" />Dynamic coordinates</span></div><div className="relative aspect-[4/5] overflow-hidden rounded-xl bg-ink-100">{source ? <img src={source.url} alt="Uploaded product label" className="w-full h-full object-cover" /> : <div className="w-full h-full grid place-items-center text-ink-500">No product image</div>}{annotations.map((item) => { const cfg = style(item.status); return <div key={item.id} className={'absolute border-2 rounded-lg bg-white/10 ' + cfg.border} style={{ left: item.x + '%', top: item.y + '%', width: item.w + '%', height: item.h + '%' }}><span className={'absolute -top-6 left-0 badge text-[10px] ' + cfg.badge}>{item.label}</span></div>; })}</div><div className="mt-4 flex flex-wrap gap-2"><Badge status="COMPLIANT" /><Badge status="VIOLATION" /><Badge status="UNABLE_TO_VERIFY" /></div></section><section className="space-y-4"><div className="card p-5"><div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><SearchCheck className="w-5 h-5" /></div><div><h2 className="font-semibold text-ink-900">MRP analysis</h2><p className="text-sm text-ink-500">Mock advanced finding</p></div></div><div className="mt-4 rounded-xl bg-warning-50 border border-warning-200 p-4"><Badge status="UNABLE_TO_VERIFY" /><p className="text-sm text-warning-800 mt-3">MRP was not visible in the uploaded images. Add a clear price-panel image before a determination.</p></div></div><div className="card p-5"><h2 className="font-semibold text-ink-900">Detailed findings</h2><div className="mt-4 space-y-4">{annotations.map((item) => <div key={item.id} className="flex gap-3"><div className={'w-2.5 h-2.5 rounded-full mt-1.5 ' + (item.status === 'COMPLIANT' ? 'bg-success-500' : item.status === 'VIOLATION' ? 'bg-danger-500' : 'bg-warning-500')} /><div><p className="text-sm font-medium text-ink-800">{item.label}</p><p className="text-sm text-ink-600 mt-0.5">{item.status === 'VIOLATION' ? 'Mock issue marker; future rules output will provide requirement and evidence.' : item.status === 'UNABLE_TO_VERIFY' ? 'Additional evidence required; no violation is inferred.' : 'Example evidence region.'}</p></div></div>)}</div></div></section></div></div>;
}

function Report({ images, back, result }: { images: Array<ImageItem | null>; back: () => void; result?: ScanApiResponse | null }) {
  const checks = result?.checks ?? mockChecks;
  const violations = checks.filter((x) => x.status === 'VIOLATION').length;
  const review = checks.filter((x) => x.status === 'UNABLE_TO_VERIFY' || x.status === 'OFFICER_REVIEW_REQUIRED' || x.status === 'NOT_APPLICABLE').length;
  const overallStatus = result?.overall_status ?? 'UNABLE_TO_VERIFY';
  const overallLabel = overallStatus === 'COMPLIANT' ? 'COMPLIANT' : overallStatus === 'VIOLATION' ? 'VIOLATION' : overallStatus === 'NOT_APPLICABLE' ? 'NOT APPLICABLE' : overallStatus === 'OFFICER_REVIEW_REQUIRED' ? 'OFFICER REVIEW REQUIRED' : 'REQUIRES REVIEW';
  return <div className="max-w-6xl mx-auto"><PageHeader title="Compliance report" subtitle={result ? 'Image analysis completed through the secure Gemini backend.' : 'Mock result layout — no image analysis has been performed.'} actions={<button onClick={back} className="btn-secondary"><RotateCcw className="w-4 h-4" />Scan another product</button>} /><InfoNote>{result ? 'Gemini extracted package text and the Python compliance_engine applied the legal rules.' : 'Sample statuses demonstrate future compliance_engine responses; they are not conclusions about your product.'}</InfoNote><section className="card p-5 sm:p-6 mt-6"><div className="flex flex-col sm:flex-row sm:items-center gap-4"><div className="w-14 h-14 rounded-2xl bg-warning-50 text-warning-700 grid place-items-center"><AlertCircle className="w-7 h-7" /></div><div className="flex-1"><p className="text-xs uppercase tracking-wide font-semibold text-ink-500">Overall status</p><h2 className="text-2xl font-bold text-ink-900 mt-1">{overallLabel}</h2><p className="text-sm text-ink-600 mt-1">{result ? 'The backend applied the legal rules to the extracted package declarations.' : 'Some declarations need evidence or product classification.'}</p></div><div className="grid grid-cols-2 gap-3 sm:w-64"><div className="rounded-xl bg-danger-50 p-3"><p className="text-xl font-bold text-danger-700">{violations}</p><p className="text-xs text-danger-700 mt-1">Violation</p></div><div className="rounded-xl bg-warning-50 p-3"><p className="text-xl font-bold text-warning-700">{review}</p><p className="text-xs text-warning-700 mt-1">Need review</p></div></div></div></section><section className="mt-6"><div className="flex items-center justify-between mb-3"><h2 className="font-semibold text-ink-900">Individual checks</h2><span className="text-sm text-ink-500">{checks.length} declarations</span></div><div className="space-y-3">{checks.map((check) => <CheckRow key={check.id} check={check} images={images} />)}</div></section></div>;
}

export function ScanProduct() {
  const [slots, setSlots] = useState<Array<ImageItem | null>>([null, null]);
  const [stage, setStage] = useState<Stage>('upload');
  const [mode, setMode] = useState<Mode>('report');
  const [target, setTarget] = useState(0);
  const [result, setResult] = useState<ScanApiResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null); const cameraRef = useRef<HTMLInputElement>(null); const count = slots.filter(Boolean).length;
  const choose = (index: number, camera = false) => { setTarget(index); (camera ? cameraRef : fileRef).current?.click(); };
  const storeFile = (file: File | undefined, index = target) => { if (!file || !file.type.startsWith('image/')) return; const reader = new FileReader(); reader.onload = () => setSlots((old) => old.map((item, i) => i === index ? { id: String(Date.now()) + '-' + i, name: file.name, url: reader.result as string } : item)); reader.readAsDataURL(file); };
  const input = (event: ChangeEvent<HTMLInputElement>) => { storeFile(event.target.files?.[0]); event.target.value = ''; };
  const drop = (index: number, event: DragEvent<HTMLDivElement>) => { event.preventDefault(); storeFile(event.dataTransfer.files?.[0], index); };
  const remove = (index: number) => setSlots((old) => index < 2 ? old.map((item, i) => i === index ? null : item) : old.filter((_, i) => i !== index));
  const reset = () => { setSlots([null, null]); setStage('upload'); setMode('report'); setResult(null); setUploadError(null); };

  const runScan = async (scanMode: Mode) => {
    const selected = slots.filter(Boolean) as ImageItem[];
    if (selected.length < 2) {
      setUploadError('At least two package images are required for a compliance scan.');
      return;
    }

    setMode(scanMode);
    setIsSubmitting(true);
    setUploadError(null);
    setStage('processing');

    try {
      const formData = new FormData();
      for (const item of selected) {
        const response = await fetch(item.url);
        const blob = await response.blob();
        const file = new File([blob], item.name || `package-${Date.now()}.png`, { type: blob.type || 'image/png' });
        formData.append('images', file, file.name);
      }

      const request = await fetch('http://127.0.0.1:8000/api/scan', { method: 'POST', body: formData });
      let payload: ScanApiResponse | null = null;
      try {
        payload = (await request.json()) as ScanApiResponse;
      } catch {
        payload = null;
      }

      if (!request.ok) {
        const detail = payload && typeof payload === 'object' && 'detail' in payload ? String((payload as { detail?: unknown }).detail ?? '') : '';
        const message = detail || 'The backend could not process the uploaded package images.';
        throw new Error(message);
      }

      if (!payload || !Array.isArray(payload.checks) || !payload.overall_status) {
        throw new Error('The backend returned an invalid scan result.');
      }

      setUploadError(null);
      setResult(payload);
      setStage(scanMode === 'advanced' ? 'advanced' : 'report');
    } catch (error) {
      console.error(error);
      setResult(null);
      setStage('upload');
      const errMessage = error instanceof Error ? error.message : 'Unable to connect to the secure backend.';
      const friendlyMessage = errMessage === 'Failed to fetch' || errMessage.includes('fetch')
        ? 'Unable to connect to the backend. Start the Python API on http://127.0.0.1:8000 and ensure GEMINI_API_KEY is set in the project .env file.'
        : errMessage;
      setUploadError(friendlyMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (stage === 'processing') return <Processing mode={mode} results={() => setStage(mode === 'advanced' ? 'advanced' : 'report')} back={() => setStage('upload')} />;
  if (stage === 'report') return <Report images={slots} back={reset} result={result} />;
  if (stage === 'advanced') return <Advanced images={slots} back={reset} />;
  return <div className="max-w-6xl mx-auto"><PageHeader title="Product Compliance Scan" subtitle="Capture at least two package surfaces for a more complete Legal Metrology review." /><div className="grid lg:grid-cols-[1fr_300px] gap-6 items-start"><section className="card p-5 sm:p-6"><div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5"><div><h2 className="font-semibold text-ink-900">Upload package images</h2><p className="text-sm text-ink-500 mt-1">Front, back, price panel, and complaint-contact panels are useful.</p></div><span className={'badge ' + (count >= 2 ? 'bg-success-50 text-success-700' : 'bg-warning-50 text-warning-700')}><ImageIcon className="w-3.5 h-3.5" />{count}/2 minimum</span></div><div className="grid sm:grid-cols-2 gap-4">{slots.map((item, index) => <ImageSlot key={item?.id ?? 'empty-' + index} image={item} index={index} choose={() => choose(index)} camera={() => choose(index, true)} drop={(e) => drop(index, e)} remove={() => remove(index)} />)}</div><button onClick={() => setSlots((old) => [...old, null])} className="btn-secondary w-full mt-4 py-3"><Plus className="w-4 h-4" />Add another image</button><div className="mt-4"><InfoNote><strong>Minimum 2 images required.</strong> A declaration not visible in these images is unable to verify—not automatically a violation.</InfoNote></div>{uploadError && <div className="mt-4 rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700">{uploadError}</div>}<input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={input} /><input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={input} /></section><aside className="card p-5 lg:sticky lg:top-6"><div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><ShieldCheck className="w-5 h-5" /></div><h2 className="font-semibold text-ink-900 mt-4">Choose scan type</h2><p className="text-sm text-ink-500 mt-1">Buttons activate after two images are attached.</p><div className="mt-5 space-y-3"><button disabled={count < 2 || isSubmitting} onClick={() => void runScan('report')} className="btn-primary w-full py-3"><FileText className="w-4 h-4" />{isSubmitting ? 'Scanning...' : 'Generate Report'}</button><button disabled={count < 2 || isSubmitting} onClick={() => void runScan('advanced')} className="btn-secondary w-full py-3"><Sparkles className="w-4 h-4 text-brand-600" />Advanced Scan</button></div><div className="mt-5 pt-5 border-t border-ink-100 text-sm text-ink-600 space-y-3"><p><strong className="text-ink-800">Generate Report</strong><br />General declaration review.</p><p><strong className="text-ink-800">Advanced Scan</strong><br />MRP review and annotation-ready evidence.</p></div>{count < 2 && <div className="mt-4 flex gap-2 text-xs text-warning-800 bg-warning-50 border border-warning-200 rounded-xl p-3"><Info className="w-4 h-4 shrink-0" />Add {2 - count} more image{2 - count === 1 ? '' : 's'} to continue.</div>}</aside></div></div>;
}
