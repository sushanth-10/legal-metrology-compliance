import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { AlertCircle, ArrowLeft, Camera, CheckCircle2, ChevronDown, ChevronUp, Circle, CircleAlert, FileImage, FileText, ImageIcon, Info, Loader2, Plus, RotateCcw, ScanLine, ShieldCheck, Sparkles, Upload, X } from 'lucide-react';
import { InfoNote, PageHeader } from '@/components/ui';
import { useApp } from '@/store';
import { apiBaseUrl, apiFetch, apiJson } from '@/lib/api';
import type { GeneratedReport, Scan } from '@/types';

type Mode = 'report' | 'advanced';
type Stage = 'upload' | 'processing' | 'report' | 'advanced';
type Status = 'COMPLIANT' | 'VIOLATION' | 'UNABLE_TO_VERIFY' | 'NOT_APPLICABLE' | 'OFFICER_REVIEW_REQUIRED';
type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'unable_to_verify';
type ImageItem = { id: string; name: string; url: string; file?: File };
type CameraState = {
  open: boolean;
  slotIndex: number | null;
  stream: MediaStream | null;
  capturedDataUrl: string | null;
  error: string | null;
};
type ScanApiResponse = {
  overall_status: Status;
  checks: Check[];
  coverage?: { overall?: string; minimum_required_surfaces_covered?: boolean; notes?: string };
  summary?: { total_checks: number; compliant: number; violations: number; review: number };
  scan?: Scan;
  report_id?: string | null;
};

const allowedImageTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);
const maxImageBytes = 10 * 1024 * 1024;

function normalizeScan(scan: Scan): Scan {
  const normalizeImageList = (values?: string[]) =>
    values
      ? values.map((value) => (value && value.startsWith('/') ? `${apiBaseUrl()}${value}` : value))
      : undefined;

  const imageUrls = normalizeImageList(scan.images);
  const primaryImage = scan.image?.startsWith('/') ? `${apiBaseUrl()}${scan.image}` : scan.image;
  return {
    ...scan,
    image: primaryImage,
    images: imageUrls && imageUrls.length > 0 ? imageUrls : primaryImage ? [primaryImage] : undefined,
  };
}

type Check = { id: string; label: string; status: Status; value: string; reference: string; explanation: string; sourceImage: number | null };

const steps = ['Images uploaded', 'Image quality checked', 'Reading product label', 'Extracting product information', 'Checking mandatory declarations', 'Applying Legal Metrology rules', 'Generating compliance report'];

function style(status: Status) {
  if (status === 'COMPLIANT') return { badge: 'bg-success-50 text-success-700', border: 'border-success-400', icon: CheckCircle2 };
  if (status === 'VIOLATION') return { badge: 'bg-danger-50 text-danger-700', border: 'border-danger-400', icon: CircleAlert };
  if (status === 'OFFICER_REVIEW_REQUIRED') return { badge: 'bg-brand-50 text-brand-700', border: 'border-brand-400', icon: ShieldCheck };
  if (status === 'NOT_APPLICABLE') return { badge: 'bg-ink-100 text-ink-700', border: 'border-ink-300', icon: Info };
  return { badge: 'bg-warning-50 text-warning-700', border: 'border-warning-400', icon: AlertCircle };
}
function Badge({ status }: { status: Status }) {
  const cfg = style(status); const Icon = cfg.icon;
  const label = status === 'COMPLIANT' ? 'COMPLIANT' : status === 'VIOLATION' ? 'NON-COMPLIANT' : status === 'NOT_APPLICABLE' ? 'UNABLE TO VERIFY' : 'UNABLE TO VERIFY';
  return <span className={'badge ' + cfg.badge}><Icon className="w-3.5 h-3.5" />{label}</span>;
}

function ImageSlot({ image, index, choose, camera, drop, remove }: { image: ImageItem | null; index: number; choose: () => void; camera: () => void; drop: (e: DragEvent<HTMLDivElement>) => void; remove: () => void }) {
  return <div onDragOver={(e) => e.preventDefault()} onDrop={drop} className={'relative min-h-52 rounded-2xl border-2 border-dashed p-4 ' + (image ? 'border-ink-200 bg-ink-50' : 'border-ink-300 bg-white hover:border-brand-400 hover:bg-brand-50/30')}>
    {image ? <><img src={image.url} alt={'Uploaded label ' + (index + 1)} className="h-40 w-full rounded-xl object-cover bg-ink-100" /><div className="mt-3 flex gap-2 min-w-0"><FileImage className="w-4 h-4 text-brand-600 shrink-0" /><span className="text-sm font-medium text-ink-700 truncate">{image.name}</span></div><div className="mt-3 flex gap-2"><button onClick={choose} className="btn-secondary flex-1 py-2"><Upload className="w-3.5 h-3.5" />Replace</button><button aria-label={'Remove image ' + (index + 1)} onClick={remove} className="btn-secondary px-3 py-2 text-danger-600"><X className="w-4 h-4" /></button></div></> :
      <div className="min-h-48 flex flex-col items-center justify-center text-center"><div className="w-12 h-12 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><ImageIcon className="w-6 h-6" /></div><h3 className="font-semibold text-ink-800 mt-3">Label image {index + 1}</h3><p className="text-xs text-ink-500 mt-1 max-w-52">Upload a different package side for better coverage.</p><div className="mt-4 flex gap-2"><button onClick={choose} className="btn-secondary py-2"><Upload className="w-3.5 h-3.5" />Upload</button><button onClick={camera} className="btn-secondary py-2"><Camera className="w-3.5 h-3.5" />Photo</button></div></div>}
  </div>;
}

function Processing({ mode, results, back }: { mode: Mode; results: () => void; back: () => void }) {
  const [state] = useState<ProcessingStatus>('processing');
  const [progressIndex, setProgressIndex] = useState(2);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setProgressIndex((value) => (value >= steps.length - 1 ? steps.length - 1 : value + 1));
    }, 900);
    return () => window.clearInterval(timer);
  }, []);

  return <div className="max-w-5xl mx-auto"><PageHeader title={mode === 'advanced' ? 'Advanced Scan in progress' : 'Generating compliance report'} subtitle="OCR, Gemini extraction, and Python compliance checks are running securely." /><div className="grid lg:grid-cols-[1.15fr_.85fr] gap-6"><section className="card p-5 sm:p-7"><div className="flex items-center gap-3 pb-5 border-b border-ink-100"><div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><ScanLine className="w-5 h-5" /></div><div><h2 className="font-semibold text-ink-900">Processing timeline</h2><p className="text-sm text-ink-500">Fast OCR + structured extraction is running on the secure backend.</p></div></div><ol className="mt-6">{steps.map((label, i) => <li key={label} className="flex gap-3 min-h-14"><div className="flex flex-col items-center">{i < progressIndex ? <CheckCircle2 className="w-5 h-5 text-success-500" /> : i === progressIndex ? <Loader2 className="w-5 h-5 text-brand-600 animate-spin" /> : <Circle className="w-5 h-5 text-ink-300" />}{i < steps.length - 1 && <div className={'w-px flex-1 my-1 ' + (i < progressIndex ? 'bg-success-200' : 'bg-ink-200')} />}</div><div className="pb-5"><p className={'text-sm font-medium ' + (i < progressIndex ? 'text-ink-800' : i === progressIndex ? 'text-brand-700' : 'text-ink-400')}>{label}</p>{i === progressIndex && <p className="text-xs text-ink-500 mt-0.5">OCR and compliance checks are in progress</p>}</div></li>)}</ol></section><aside className="space-y-4"><div className="card p-5"><span className="badge bg-brand-50 text-brand-700"><Loader2 className="w-3.5 h-3.5 animate-spin" />{state}</span><h2 className="font-semibold text-ink-900 mt-4">Live data flow</h2><p className="text-sm text-ink-600 mt-2 leading-6">Images → OCR text → Gemini extraction → structured observations → Python compliance_engine → results.</p><p className="text-sm text-ink-600 mt-2 leading-6">Gemini extracts only; Python rules determine compliance.</p></div><InfoNote>The result screen will preserve the actual extracted values, explanations, and evidence returned by the backend.</InfoNote><button onClick={results} className="btn-primary w-full py-3"><FileText className="w-4 h-4" />View result</button><button onClick={back} className="btn-secondary w-full py-3"><ArrowLeft className="w-4 h-4" />Back to images</button></aside></div></div>;
}

function CheckRow({ check, images }: { check: Check; images: Array<ImageItem | null> }) {
  const [open, setOpen] = useState(false); const [issue, setIssue] = useState<'missing' | 'no-label' | 'other' | null>(null); const [note, setNote] = useState(''); const [saved, setSaved] = useState(false);
  const source = check.sourceImage === null ? null : images[check.sourceImage];
  return <article className="border border-ink-200 rounded-xl overflow-hidden"><button onClick={() => setOpen(!open)} className="w-full text-left p-4 flex items-start gap-3 hover:bg-ink-50"><Badge status={check.status} /><div className="flex-1 min-w-0"><p className="font-semibold text-ink-900">{check.label}</p><p className="text-sm text-ink-500 mt-0.5 truncate">{check.value}</p></div>{open ? <ChevronUp className="w-4 h-4 text-ink-500 mt-1" /> : <ChevronDown className="w-4 h-4 text-ink-500 mt-1" />}</button>{open && <div className="border-t border-ink-100 p-4 bg-ink-50/50 grid md:grid-cols-[1fr_220px] gap-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Applicable requirement</p><p className="text-sm text-ink-700 mt-1">{check.reference}</p><p className="text-xs font-semibold uppercase tracking-wide text-ink-500 mt-4">Explanation</p><p className="text-sm text-ink-700 mt-1 leading-6">{check.explanation}</p>{check.id === 'mrp' && check.status === 'UNABLE_TO_VERIFY' && <div className="mt-4 rounded-xl border border-warning-200 bg-warning-50 p-3"><p className="text-sm font-semibold text-warning-800">Tell us what you observed</p><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => { setIssue('missing'); setSaved(false); }} className="btn-secondary py-2">MRP appears to be missing</button><button onClick={() => { setIssue('no-label'); setSaved(false); }} className="btn-secondary py-2">No label/declaration visible</button><button onClick={() => { setIssue('other'); setSaved(false); }} className="btn-secondary py-2">Other issue</button></div>{issue === 'other' && <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} className="input mt-3 resize-y" placeholder="Describe the issue for future review…" />}{issue && <button disabled={issue === 'other' && !note.trim()} onClick={() => setSaved(true)} className="btn-primary mt-3 py-2">Continue</button>}{saved && <p className="text-xs text-success-700 font-medium mt-3">Observation recorded for future review. Status is unchanged.</p>}</div>}</div><div><p className="text-xs font-semibold uppercase tracking-wide text-ink-500 mb-2">Evidence / source</p>{source ? <img src={source.url} alt={'Evidence for ' + check.label} className="w-full aspect-[4/3] object-cover rounded-lg border border-ink-200" /> : <div className="aspect-[4/3] rounded-lg border border-dashed border-ink-300 bg-white grid place-items-center p-3 text-center text-xs text-ink-500">No source image established</div>}</div></div>}</article>;
}

function Advanced({ images, back, result }: { images: Array<ImageItem | null>; back: () => void; result?: ScanApiResponse | null }) {
  const source = images.find(Boolean);
  const checks = result?.checks || [];
  return <div className="max-w-6xl mx-auto"><PageHeader title="Advanced scan findings" subtitle="Actual findings returned by the backend compliance assessment." actions={<button onClick={back} className="btn-secondary"><RotateCcw className="w-4 h-4" />Scan another product</button>} /><InfoNote>Advanced mode uses the same persisted scan result and compliance_engine classifications. No additional frontend classification is applied.</InfoNote><div className="grid xl:grid-cols-[.85fr_1.15fr] gap-6 mt-6"><section className="card p-4 sm:p-5"><h2 className="font-semibold text-ink-900 mb-4">Evidence image</h2>{source ? <img src={source.url} alt="Uploaded product label" className="w-full max-h-[560px] object-contain rounded-xl bg-ink-100 border border-ink-200" /> : <div className="aspect-[4/5] grid place-items-center text-ink-500">No product image</div>}<p className="text-xs text-ink-500 mt-3">{images.filter(Boolean).length} uploaded evidence image(s)</p></section><section className="card p-5"><h2 className="font-semibold text-ink-900">Detailed findings</h2><div className="mt-4 space-y-3">{checks.length ? checks.map((check) => <div key={check.id} className="border border-ink-200 rounded-xl p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-medium text-ink-900">{check.label}</p><p className="text-sm text-ink-600 mt-1">{check.value}</p></div><Badge status={check.status} /></div><p className="text-xs text-ink-500 mt-3">{check.reference}</p></div>) : <p className="text-sm text-ink-500">No backend findings are available for this scan.</p>}</div></section></div></div>;
}

function Report({ images, back, result }: { images: Array<ImageItem | null>; back: () => void; result?: ScanApiResponse | null }) {
  const checks = result?.checks ?? [];
  const violations = checks.filter((x) => x.status === 'VIOLATION').length;
  const review = checks.filter((x) => x.status === 'UNABLE_TO_VERIFY' || x.status === 'OFFICER_REVIEW_REQUIRED' || x.status === 'NOT_APPLICABLE').length;
  const overallStatus = result?.overall_status ?? 'UNABLE_TO_VERIFY';
  const overallLabel = overallStatus === 'COMPLIANT' ? 'COMPLIANT' : overallStatus === 'VIOLATION' ? 'NON-COMPLIANT' : 'UNABLE TO VERIFY';
  return <div className="max-w-6xl mx-auto"><PageHeader title="Compliance report" subtitle={result ? 'Image analysis completed through the secure Gemini backend.' : 'No persisted scan result is available.'} actions={<button onClick={back} className="btn-secondary"><RotateCcw className="w-4 h-4" />Scan another product</button>} /><InfoNote>{result ? 'Gemini extracted package text and the Python compliance_engine applied the legal rules.' : 'Run a scan to view actual findings.'}</InfoNote><section className="card p-5 sm:p-6 mt-6"><div className="flex flex-col sm:flex-row sm:items-center gap-4"><div className="w-14 h-14 rounded-2xl bg-warning-50 text-warning-700 grid place-items-center"><AlertCircle className="w-7 h-7" /></div><div className="flex-1"><p className="text-xs uppercase tracking-wide font-semibold text-ink-500">Overall status</p><h2 className="text-2xl font-bold text-ink-900 mt-1">{overallLabel}</h2></div><div className="grid grid-cols-2 gap-3 sm:w-64"><div className="rounded-xl bg-danger-50 p-3"><p className="text-xl font-bold text-danger-700">{violations}</p><p className="text-xs text-danger-700 mt-1">Violation</p></div><div className="rounded-xl bg-warning-50 p-3"><p className="text-xl font-bold text-warning-700">{review}</p><p className="text-xs text-warning-700 mt-1">Need review</p></div></div></div></section><section className="mt-6"><div className="flex items-center justify-between mb-3"><h2 className="font-semibold text-ink-900">Individual checks</h2><span className="text-sm text-ink-500">{checks.length} findings</span></div><div className="space-y-3">{checks.map((check) => <CheckRow key={check.id} check={check} images={images} />)}</div></section></div>;
}

function PersistedReportActions({ result }: { result: ScanApiResponse | null }) {
  const { role, addReport, setPage, showToast } = useApp();
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState<GeneratedReport | null>(null);
  if (!['organization', 'officer'].includes(role) || !result?.scan) return null;
  const generate = async () => {
    setIsGenerating(true);
    try {
      const report = await apiJson<GeneratedReport>(`/api/reports/${encodeURIComponent(result.scan!.id)}`, { method: 'POST' });
      addReport(report);
      setGeneratedReport(report);
      showToast('success', 'Official PDF report generated and saved.');
    } catch (error) {
      showToast('error', error instanceof Error ? error.message : 'Unable to generate the PDF report.');
    } finally {
      setIsGenerating(false);
    }
  };
  return <div className="max-w-6xl mx-auto mt-6 card p-5 flex flex-col sm:flex-row sm:items-center gap-3"><div className="flex-1"><p className="font-semibold text-ink-900">Official compliance report</p><p className="text-sm text-ink-500 mt-1">Generate a PDF from this persisted scan and its actual rule results.</p></div><button onClick={() => void generate()} disabled={isGenerating} className="btn-primary py-2.5">{isGenerating ? 'Generating…' : generatedReport ? 'Generate Updated Report' : 'Generate Report'}</button>{generatedReport && <button onClick={() => setPage('reports')} className="btn-secondary py-2.5">View Report</button>}</div>;
}

export function ScanProduct() {
  const { addScan } = useApp();
  const [slots, setSlots] = useState<Array<ImageItem | null>>([null, null]);
  const [stage, setStage] = useState<Stage>('upload');
  const [mode, setMode] = useState<Mode>('report');
  const [target, setTarget] = useState(0);
  const [result, setResult] = useState<ScanApiResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [cameraState, setCameraState] = useState<CameraState>({
    open: false,
    slotIndex: null,
    stream: null,
    capturedDataUrl: null,
    error: null,
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const count = slots.filter(Boolean).length;

  const stopCameraStream = () => {
    if (cameraState.stream) {
      cameraState.stream.getTracks().forEach((track) => track.stop());
    }
  };

  const closeCamera = () => {
    stopCameraStream();
    setCameraState({ open: false, slotIndex: null, stream: null, capturedDataUrl: null, error: null });
  };

  const choose = (index: number, useCamera = false) => {
    setTarget(index);
    if (useCamera) {
      void openCamera(index);
      return;
    }
    fileRef.current?.click();
  };

  const openCamera = async (index: number) => {
    stopCameraStream();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraState({ open: false, slotIndex: null, stream: null, capturedDataUrl: null, error: 'This browser does not support camera access. Please use the Upload option instead.' });
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
        },
        audio: false,
      });
      setCameraState({ open: true, slotIndex: index, stream, capturedDataUrl: null, error: null });
    } catch (error) {
      const message = error instanceof DOMException && error.name === 'NotAllowedError'
        ? 'Camera permission was denied. Upload remains available and the scan workflow is unaffected.'
        : error instanceof DOMException && error.name === 'NotFoundError'
        ? 'No camera is available on this device.'
        : 'Camera initialization failed. Please try again or use the Upload option instead.';
      setCameraState({ open: false, slotIndex: null, stream: null, capturedDataUrl: null, error: message });
    }
  };

  useEffect(() => {
    if (!cameraState.open || !videoRef.current || !cameraState.stream) return;
    videoRef.current.srcObject = cameraState.stream;
    videoRef.current.play().catch(() => undefined);
  }, [cameraState.open, cameraState.stream]);

  useEffect(() => {
    return () => {
      if (cameraState.stream) {
        cameraState.stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [cameraState.stream]);

  const storeFile = (file: File | undefined, index = target) => {
    if (!file) return;
    if (!allowedImageTypes.has(file.type)) {
      setUploadError('Please upload a JPG, PNG, or WebP image.');
      return;
    }
    if (file.size === 0) {
      setUploadError(`${file.name || 'The selected image'} is empty.`);
      return;
    }
    if (file.size > maxImageBytes) {
      setUploadError(`${file.name || 'The selected image'} exceeds the 10 MB size limit.`);
      return;
    }
    setUploadError(null);
    const reader = new FileReader();
    reader.onload = () => setSlots((old) => old.map((item, i) => i === index ? { id: String(Date.now()) + '-' + i, name: file.name, url: reader.result as string, file } : item));
    reader.readAsDataURL(file);
  };
  const input = (event: ChangeEvent<HTMLInputElement>) => { storeFile(event.target.files?.[0]); event.target.value = ''; };
  const drop = (index: number, event: DragEvent<HTMLDivElement>) => { event.preventDefault(); storeFile(event.dataTransfer.files?.[0], index); };
  const remove = (index: number) => setSlots((old) => index < 2 ? old.map((item, i) => i === index ? null : item) : old.filter((_, i) => i !== index));
  const reset = () => { setSlots([null, null]); setStage('upload'); setMode('report'); setResult(null); setUploadError(null); };

  const dataUrlToFile = (dataUrl: string, filename: string) => {
    const [header, content] = dataUrl.split(',');
    const mime = header.match(/data:(image\/[a-zA-Z0-9.+-]+);base64/)?.[1] ?? 'image/jpeg';
    const binary = atob(content || '');
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new File([bytes], filename, { type: mime });
  };

  const captureCameraPhoto = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement('canvas');
    const width = video.videoWidth || 1200;
    const height = video.videoHeight || 900;
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    stopCameraStream();
    setCameraState((prev) => ({ ...prev, stream: null, capturedDataUrl: dataUrl }));
  };

  const retakeCameraPhoto = () => {
    if (cameraState.slotIndex === null) return;
    stopCameraStream();
    setCameraState({ open: false, slotIndex: cameraState.slotIndex, stream: null, capturedDataUrl: null, error: null });
    void openCamera(cameraState.slotIndex);
  };

  const confirmCameraPhoto = () => {
    if (!cameraState.capturedDataUrl || cameraState.slotIndex === null) return;
    const file = dataUrlToFile(cameraState.capturedDataUrl, `camera-${cameraState.slotIndex + 1}.jpg`);
    closeCamera();
    storeFile(file, cameraState.slotIndex);
  };

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
      const files: File[] = [];
      const fingerprints = new Set<string>();
      for (const item of selected) {
        if (!item.file) {
          throw new Error(`Please reselect ${item.name || 'the image'} before generating the report.`);
        }
        const file = item.file;
        const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
        const fingerprint = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
        if (!fingerprints.has(fingerprint)) {
          fingerprints.add(fingerprint);
          files.push(file);
        }
      }
      if (files.length < 2) {
        throw new Error('Please upload at least two different package images.');
      }
      for (const file of files) {
        formData.append('images', file, file.name);
      }

      const request = await apiFetch('/api/scan', { method: 'POST', body: formData });
      let payload: ScanApiResponse | null = null;
      try {
        payload = (await request.json()) as ScanApiResponse;
      } catch {
        payload = null;
      }

      if (!request.ok) {
        const detail = payload && typeof payload === 'object' && 'detail' in payload ? String((payload as { detail?: unknown }).detail ?? '') : '';
        const message = detail || 'The backend could not process the uploaded package images.';
        throw new Error(request.status >= 500 ? `Gemini/backend analysis failed: ${message}` : message);
      }

      if (!payload || !Array.isArray(payload.checks) || !payload.overall_status) {
        throw new Error('The backend returned an invalid scan result.');
      }

      setUploadError(null);
      if (payload.scan) {
        const normalizedScan = normalizeScan(payload.scan);
        addScan(normalizedScan);
      }
      setResult(payload);
      setStage(scanMode === 'advanced' ? 'advanced' : 'report');
    } catch (error) {
      console.error(error);
      setResult(null);
      setStage('upload');
      const errMessage = error instanceof Error ? error.message : 'Unable to connect to the secure backend.';
      const friendlyMessage = errMessage === 'Failed to fetch' || errMessage.includes('fetch')
        ? 'Unable to connect to the backend. Start the Python API on the configured API port and check the backend environment configuration.'
        : errMessage;
      setUploadError(friendlyMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (stage === 'processing') return <Processing mode={mode} results={() => setStage(mode === 'advanced' ? 'advanced' : 'report')} back={() => setStage('upload')} />;
  if (stage === 'report') return <><Report images={slots} back={reset} result={result} /><PersistedReportActions result={result} /></>;
  if (stage === 'advanced') return <Advanced images={slots} back={reset} result={result} />;
  return <div className="max-w-6xl mx-auto"><PageHeader title="Product Compliance Scan" subtitle="Capture at least two package surfaces for a more complete Legal Metrology review." /><div className="grid lg:grid-cols-[1fr_300px] gap-6 items-start"><section className="card p-5 sm:p-6"><div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5"><div><h2 className="font-semibold text-ink-900">Upload package images</h2><p className="text-sm text-ink-500 mt-1">Front, back, price panel, and complaint-contact panels are useful.</p></div><span className={'badge ' + (count >= 2 ? 'bg-success-50 text-success-700' : 'bg-warning-50 text-warning-700')}><ImageIcon className="w-3.5 h-3.5" />{count}/2 minimum</span></div><div className="grid sm:grid-cols-2 gap-4">{slots.map((item, index) => <ImageSlot key={item?.id ?? 'empty-' + index} image={item} index={index} choose={() => choose(index)} camera={() => choose(index, true)} drop={(e) => drop(index, e)} remove={() => remove(index)} />)}</div><button onClick={() => setSlots((old) => [...old, null])} className="btn-secondary w-full mt-4 py-3"><Plus className="w-4 h-4" />Add another image</button><div className="mt-4 rounded-xl border border-ink-200 bg-ink-50 p-4"><div className="flex items-center gap-2"><Info className="w-4 h-4 text-brand-600" /><h3 className="font-semibold text-ink-900">Photo Tips</h3></div><ul className="mt-3 space-y-1.5 text-sm text-ink-600 list-disc pl-5"><li>Upload clear, high-resolution photos.</li><li>Capture the front and back of the package whenever possible.</li><li>Ensure text and declarations are readable and not blurry.</li><li>Avoid glare, reflections, shadows, folded packaging, and obstructed labels.</li><li>Include the complete package surface in the photo.</li><li>For multiple images, upload different sides or angles of the same package.</li></ul><p className="mt-3 text-xs text-ink-500">Better-quality images improve extraction and compliance assessment accuracy.</p></div><div className="mt-4"><InfoNote><strong>Minimum 2 images required.</strong> A declaration not visible in these images is unable to verify—not automatically a violation.</InfoNote></div>{uploadError && <div className="mt-4 rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700">{uploadError}</div>}{cameraState.error && <div className="mt-4 rounded-xl border border-warning-200 bg-warning-50 p-3 text-sm text-warning-800">{cameraState.error}</div>}<input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={input} /></section><aside className="card p-5 lg:sticky lg:top-6"><div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 grid place-items-center"><ShieldCheck className="w-5 h-5" /></div><h2 className="font-semibold text-ink-900 mt-4">Choose scan type</h2><p className="text-sm text-ink-500 mt-1">Buttons activate after two images are attached.</p><div className="mt-5 space-y-3"><button disabled={count < 2 || isSubmitting} onClick={() => void runScan('report')} className="btn-primary w-full py-3"><FileText className="w-4 h-4" />{isSubmitting ? 'Scanning...' : 'Generate Report'}</button><button disabled={count < 2 || isSubmitting} onClick={() => void runScan('advanced')} className="btn-secondary w-full py-3"><Sparkles className="w-4 h-4 text-brand-600" />Advanced Scan</button></div><div className="mt-5 pt-5 border-t border-ink-100 text-sm text-ink-600 space-y-3"><p><strong className="text-ink-800">Generate Report</strong><br />General declaration review.</p><p><strong className="text-ink-800">Advanced Scan</strong><br />MRP review and annotation-ready evidence.</p></div>{count < 2 && <div className="mt-4 flex gap-2 text-xs text-warning-800 bg-warning-50 border border-warning-200 rounded-xl p-3"><Info className="w-4 h-4 shrink-0" />Add {2 - count} more image{2 - count === 1 ? '' : 's'} to continue.</div>}</aside></div>{cameraState.open && <div className="fixed inset-0 z-50 bg-ink-950/75 flex items-center justify-center p-4"><div className="w-full max-w-md rounded-2xl border border-ink-200 bg-white shadow-2xl overflow-hidden"><div className="flex items-center justify-between border-b border-ink-100 px-4 py-3"><div><p className="text-xs uppercase tracking-wide text-ink-500">Camera capture</p><h3 className="font-semibold text-ink-900">Take a product photo</h3></div><button onClick={closeCamera} className="btn-secondary px-2.5 py-1.5"><X className="w-4 h-4" /></button></div>{cameraState.capturedDataUrl ? <div className="p-4"><div className="relative overflow-hidden rounded-xl bg-ink-100 border border-ink-200"><img src={cameraState.capturedDataUrl} alt="Captured product label preview" className="w-full h-72 object-cover" /></div></div> : <div className="p-4"><div className="relative overflow-hidden rounded-xl bg-ink-100 border border-ink-200"><video ref={videoRef} autoPlay muted playsInline className="w-full h-72 object-cover" /></div></div>}<div className="flex gap-2 p-4 pt-0"><div className="flex-1 flex gap-2">{cameraState.capturedDataUrl ? <><button onClick={retakeCameraPhoto} className="btn-secondary flex-1 py-2.5"><RotateCcw className="w-4 h-4" />Retake</button><button onClick={confirmCameraPhoto} className="btn-primary flex-1 py-2.5"><CheckCircle2 className="w-4 h-4" />Use Photo</button></> : <button onClick={captureCameraPhoto} className="btn-primary flex-1 py-2.5"><Camera className="w-4 h-4" />Take Photo</button>}</div><button onClick={closeCamera} className="btn-secondary px-3 py-2.5">Close</button></div></div></div>} </div>;
}
