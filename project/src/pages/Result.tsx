import { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileText,
  Save,
  RotateCcw,
  MapPin,
  Maximize2,
  X,
  ShieldAlert,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useApp } from '@/store';
import { Confidence } from '@/components/ui';
import { downloadReportAsPdf } from '@/lib/reporting';
import { apiJson } from '@/lib/api';
import type { ComplianceStatus, Declaration, BoundingBox, GeneratedReport } from '@/types';

const statusConfig: Record<
  ComplianceStatus,
  { label: string; bg: string; text: string; ring: string; icon: typeof CheckCircle2 }
> = {
  compliant: {
    label: 'COMPLIANT',
    bg: 'bg-success-50',
    text: 'text-success-700',
    ring: 'ring-success-200',
    icon: CheckCircle2,
  },
  'non-compliant': {
    label: 'NON-COMPLIANT',
    bg: 'bg-danger-50',
    text: 'text-danger-700',
    ring: 'ring-danger-200',
    icon: XCircle,
  },
  'needs-review': {
    label: 'NEEDS REVIEW',
    bg: 'bg-warning-50',
    text: 'text-warning-700',
    ring: 'ring-warning-200',
    icon: AlertCircle,
  },
};

function EvidenceImage({
  images,
  boxes,
  onImageChange,
  currentImageIndex,
}: {
  images: string[];
  boxes: BoundingBox[];
  onImageChange?: (index: number) => void;
  currentImageIndex?: number;
}) {
  const [open, setOpen] = useState(false);
  const imageIndex = currentImageIndex ?? 0;
  const image = images[imageIndex] || images[0];
  const totalImages = images.length;
  const showNavigation = totalImages > 1;

  const handlePrevious = () => {
    if (onImageChange && imageIndex > 0) {
      onImageChange(imageIndex - 1);
    }
  };

  const handleNext = () => {
    if (onImageChange && imageIndex < totalImages - 1) {
      onImageChange(imageIndex + 1);
    }
  };

  return (
    <>
      <div className="relative rounded-xl overflow-hidden bg-ink-100 aspect-[4/5] sm:aspect-square border border-ink-200">
        <img src={image} alt="Evidence" className="w-full h-full object-cover" />
        {boxes.map((b, i) => (
          <div
            key={i}
            className={`absolute rounded-md transition-all ${
              b.missing ? 'border-2 border-dashed border-danger-400 bg-danger-500/10' : 'border-2 border-brand-400 bg-brand-500/10'
            }`}
            style={{ left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%` }}
          >
            <span
              className={`absolute -top-5 left-0 text-[10px] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap ${
                b.missing ? 'bg-danger-500 text-white' : 'bg-brand-500 text-white'
              }`}
            >
              {b.missing ? 'Missing: ' : ''}{b.label}
            </span>
          </div>
        ))}
        
        {/* Image navigation overlay */}
        {showNavigation && (
          <>
            <button
              onClick={handlePrevious}
              disabled={imageIndex === 0}
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-ink-900/60 hover:bg-ink-900/80 disabled:opacity-50 disabled:cursor-not-allowed text-white p-2 rounded-full transition-all"
              title="Previous image"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              onClick={handleNext}
              disabled={imageIndex === totalImages - 1}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-ink-900/60 hover:bg-ink-900/80 disabled:opacity-50 disabled:cursor-not-allowed text-white p-2 rounded-full transition-all"
              title="Next image"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-ink-900/70 text-white px-3 py-1.5 rounded-full text-sm font-semibold">
              {imageIndex + 1} / {totalImages}
            </div>
          </>
        )}
      </div>
      <button
        onClick={() => setOpen(true)}
        className="btn-secondary w-full mt-3 justify-center"
      >
        <Maximize2 className="w-4 h-4" /> View Full Evidence
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 bg-ink-950/80 flex items-center justify-center p-4"
          onClick={() => setOpen(false)}
        >
          <div className="relative max-w-3xl w-full" onClick={(e) => e.stopPropagation()}>
            <button
              className="absolute -top-10 right-0 text-white/80 hover:text-white"
              onClick={() => setOpen(false)}
            >
              <X className="w-6 h-6" />
            </button>
            <div className="relative rounded-xl overflow-hidden bg-ink-100">
              <img src={image} alt="Evidence full" className="w-full h-auto" />
              {boxes.map((b, i) => (
                <div
                  key={i}
                  className={`absolute rounded-md ${
                    b.missing ? 'border-2 border-dashed border-danger-400 bg-danger-500/10' : 'border-2 border-brand-400 bg-brand-500/10'
                  }`}
                  style={{ left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%` }}
                >
                  <span
                    className={`absolute -top-5 left-0 text-[10px] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap ${
                      b.missing ? 'bg-danger-500 text-white' : 'bg-brand-500 text-white'
                    }`}
                  >
                    {b.missing ? 'Missing: ' : ''}{b.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function Result({ onScanAnother }: { onScanAnother: () => void }) {
  const { scans, selectedScanId, setPage, role, addReport, reports, showToast } = useApp();
  const scan = scans.find((s) => s.id === selectedScanId) ?? scans[0];
  const [showMrp, setShowMrp] = useState(true);
  const [previewReport, setPreviewReport] = useState<GeneratedReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  if (!scan) return null;

  const cfg = statusConfig[scan.status];
  const detected = scan.declarations.filter((d) => d.detected).length;
  const total = scan.declarations.length;
  const boxes = scan.declarations.map((d) => d.region).filter(Boolean) as BoundingBox[];
  const generatedReport = reports.find((report) => report.scanId === scan.id) ?? null;
  const images = scan.images && scan.images.length > 0 ? scan.images : [scan.image];
  const score = scan.complianceScore ?? 0;

  const handleGeneratePdfReport = async () => {
    if (role !== 'officer') return;
    try {
      const report = await apiJson<GeneratedReport>(`/api/reports/${encodeURIComponent(scan.id)}`, { method: 'POST' });
      addReport(report);
      setPreviewReport(report);
      setReportError(null);
      showToast('success', 'Official PDF report generated and saved.');
    } catch (error) {
      console.error(error);
      setReportError(error instanceof Error ? error.message : 'Unable to generate the PDF report from the current scan result.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row gap-4 items-start">
        <img
          src={scan.image}
          alt={scan.product}
          className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl object-cover border border-ink-200"
        />
        <div className="flex-1">
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-900">{scan.product}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-1.5 text-sm text-ink-500">
            <span>{scan.date}</span>
            {scan.location && (
              <>
                <span className="text-ink-300">•</span>
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" /> {scan.location}
                </span>
              </>
            )}
            {scan.category && (
              <>
                <span className="text-ink-300">•</span>
                <span>{scan.category}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Status card */}
      <div className={`card p-6 ring-1 ${cfg.ring} ${cfg.bg}`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-2xl bg-white flex items-center justify-center ${cfg.text} shadow-sm`}>
              <cfg.icon className="w-7 h-7" strokeWidth={2.2} />
            </div>
            <div>
              <p className={`text-2xl font-extrabold tracking-tight ${cfg.text}`}>{cfg.label}</p>
              <p className="text-sm text-ink-600 mt-0.5">
                {detected} of {total} mandatory declarations detected
                {scan.violations > 0 && ` • ${scan.violations} potential violation${scan.violations > 1 ? 's' : ''}`}.
              </p>
            </div>
          </div>
          <div className="text-sm text-ink-600 sm:text-right">
            <p className="font-semibold text-ink-800">Compliance Summary</p>
            <p className="max-w-xs mt-0.5">
              {scan.status === 'compliant'
                ? 'All mandatory declarations were detected and within Legal Metrology norms.'
                : scan.status === 'non-compliant'
                ? 'One or more mandatory declarations are missing or show discrepancies requiring officer verification.'
                : 'Some declarations could not be read confidently and require manual review.'}
            </p>
          </div>
        </div>
      </div>

      {/* Compliance Score card */}
      <div className="card p-6 border-l-4 border-brand-500 bg-brand-50">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-brand-700 uppercase tracking-wide">Compliance Score</p>
            <p className="text-3xl font-bold text-brand-900 mt-2">{score} / 100</p>
            <p className="text-xs text-brand-700 mt-2">This score represents a Legal Metrology compliance assessment and is not a legally binding certification. Officer review required before regulatory action.</p>
          </div>
          <div className="text-right">
            <div className="w-24 h-24 rounded-full border-4 border-brand-200 flex items-center justify-center bg-white">
              <span className="text-2xl font-bold text-brand-700">{Math.round((score / 100) * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Declaration checklist */}
        <div className="card p-5 sm:p-6">
          <h3 className="font-semibold text-ink-900 mb-4">Mandatory Declarations</h3>
          <ul className="space-y-3">
            {scan.declarations.map((d: Declaration) => (
              <li
                key={d.key}
                className="flex items-start gap-3 p-3 rounded-xl border border-ink-100 hover:border-ink-200 transition-colors"
              >
                <div className="mt-0.5 shrink-0">
                  {d.detected ? (
                    <CheckCircle2 className="w-5 h-5 text-success-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-danger-500" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-ink-800 text-sm">{d.label}</p>
                    <span
                      className={`badge text-[10px] ${
                        d.detected ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'
                      }`}
                    >
                      {d.detected ? 'Detected' : 'Not Detected'}
                    </span>
                  </div>
                  {d.detected && (
                    <>
                      <p className="text-sm text-ink-700 mt-1 break-words">{d.value}</p>
                      <div className="mt-2">
                        <Confidence value={d.confidence} />
                      </div>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Image evidence */}
        <div className="card p-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-ink-900">Image Evidence</h3>
            <span className="text-xs text-ink-500">{boxes.length} regions</span>
          </div>
          <EvidenceImage 
            images={images} 
            boxes={boxes}
            currentImageIndex={currentImageIndex}
            onImageChange={setCurrentImageIndex}
          />
          <div className="flex flex-wrap gap-2 mt-4">
            <span className="badge bg-brand-50 text-brand-700">
              <span className="w-2 h-2 rounded-full bg-brand-500" /> Detected
            </span>
            <span className="badge bg-danger-50 text-danger-700">
              <span className="w-2 h-2 rounded-full bg-danger-500" /> Missing
            </span>
          </div>
        </div>
      </div>

      {/* Violations */}
      {scan.violationList.length > 0 && (
        <div>
          <h3 className="font-semibold text-ink-900 mb-3">Potential Violations</h3>
          <div className="space-y-3">
            {scan.violationList.map((v) => (
              <div key={v.id} className="card p-5">
                <div className="flex items-start gap-3">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                      v.severity === 'high'
                        ? 'bg-danger-50 text-danger-600'
                        : v.severity === 'medium'
                        ? 'bg-warning-50 text-warning-600'
                        : 'bg-ink-100 text-ink-500'
                    }`}
                  >
                    <ShieldAlert className="w-5 h-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <p className="font-semibold text-ink-900">{v.title}</p>
                      <span
                        className={`badge text-[10px] uppercase ${
                          v.severity === 'high'
                            ? 'bg-danger-50 text-danger-700'
                            : v.severity === 'medium'
                            ? 'bg-warning-50 text-warning-700'
                            : 'bg-ink-100 text-ink-600'
                        }`}
                      >
                        {v.severity} severity
                      </span>
                    </div>
                    <p className="text-sm text-ink-600 mt-1">{v.explanation}</p>
                    <div className="mt-3 grid sm:grid-cols-2 gap-3 text-sm">
                      <div className="rounded-lg bg-ink-50 p-3">
                        <p className="text-xs font-semibold text-ink-500 uppercase tracking-wide mb-1">
                          Applicable Requirement
                        </p>
                        <p className="text-ink-700">{v.requirement}</p>
                      </div>
                      <div className="rounded-lg bg-ink-50 p-3">
                        <p className="text-xs font-semibold text-ink-500 uppercase tracking-wide mb-1">
                          Evidence
                        </p>
                        <p className="text-ink-700">{v.evidence}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Advanced MRP verification */}
      {scan.declaredMrp && (
        <div className="card p-5 sm:p-6">
          <button
            onClick={() => setShowMrp((s) => !s)}
            className="flex items-center justify-between w-full"
          >
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-brand-600" />
              <h3 className="font-semibold text-ink-900">Advanced Price Verification</h3>
              <span className="badge bg-ink-100 text-ink-600 text-[10px]">Optional</span>
            </div>
            {showMrp ? <ChevronUp className="w-4 h-4 text-ink-500" /> : <ChevronDown className="w-4 h-4 text-ink-500" />}
          </button>
          {showMrp && (
            <div className="mt-4 animate-fade-in">
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="rounded-xl border border-ink-200 p-4">
                  <p className="text-xs font-semibold text-ink-500 uppercase tracking-wide">
                    Declared MRP
                  </p>
                  <p className="text-2xl font-bold text-ink-900 mt-1">{scan.declaredMrp}</p>
                </div>
                <div className="rounded-xl border border-ink-200 p-4">
                  <p className="text-xs font-semibold text-ink-500 uppercase tracking-wide">
                    Reference MRP
                  </p>
                  <p className="text-2xl font-bold text-ink-900 mt-1">{scan.referenceMrp}</p>
                </div>
              </div>
              {scan.mrpMismatch && (
                <div className="mt-4 flex items-start gap-3 rounded-xl bg-warning-50 border border-warning-200 p-4">
                  <AlertCircle className="w-5 h-5 text-warning-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-warning-800">
                      Potential MRP Discrepancy — Requires Verification
                    </p>
                    <p className="text-sm text-warning-700 mt-1">
                      The declared MRP differs from the reference price. This is a potential
                      discrepancy that an officer must verify before any enforcement action — it is
                      not an automatic determination that the product is illegal.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {reportError && (
        <div className="rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700">
          {reportError}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3 pb-4">
        {role === 'officer' && (
          <button onClick={() => void handleGeneratePdfReport()} className="btn-primary flex-1 py-3">
            <FileText className="w-4 h-4" /> {generatedReport ? 'Generate Updated PDF' : 'Generate Report'}
          </button>
        )}
        {generatedReport && (
          <button onClick={() => setPreviewReport(generatedReport)} className="btn-secondary flex-1 py-3">
            <FileText className="w-4 h-4" /> View Report
          </button>
        )}
        {generatedReport && (
          <button onClick={() => void downloadReportAsPdf(generatedReport)} className="btn-secondary flex-1 py-3">
            <Save className="w-4 h-4" /> Download PDF
          </button>
        )}
        <button className="btn-secondary flex-1 py-3">
          <Save className="w-4 h-4" /> Save to History
        </button>
        <button onClick={onScanAnother} className="btn-secondary flex-1 py-3">
          <RotateCcw className="w-4 h-4" /> Scan Another Product
        </button>
      </div>

      <button
        onClick={() => setPage('history')}
        className="btn-ghost text-brand-600 text-sm"
      >
        Back to History
      </button>

      {previewReport && (
        <div className="fixed inset-0 z-50 bg-ink-950/70 flex items-center justify-center p-4">
          <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl border border-ink-200 bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-500">Report preview</p>
                <h3 className="font-semibold text-ink-900 text-xl mt-1">{previewReport.reportTitle}</h3>
              </div>
              <button onClick={() => setPreviewReport(null)} className="btn-secondary px-3 py-2">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-5 rounded-xl bg-ink-50 border border-ink-200 p-4 text-sm text-ink-700">
              <div className="grid sm:grid-cols-2 gap-3">
                <div><span className="font-semibold text-ink-800">Application:</span> {previewReport.applicationName}</div>
                <div><span className="font-semibold text-ink-800">Generated:</span> {new Date(previewReport.generatedAt).toLocaleString()}</div>
                <div><span className="font-semibold text-ink-800">Product:</span> {previewReport.productName}</div>
                <div><span className="font-semibold text-ink-800">Status:</span> {previewReport.overallStatus}</div>
              </div>
              <div className="mt-4 grid sm:grid-cols-3 gap-3 text-xs">
                <div className="rounded-lg bg-danger-50 p-2 text-danger-700"><strong>Violations:</strong> {previewReport.summary.violations}</div>
                <div className="rounded-lg bg-warning-50 p-2 text-warning-700"><strong>Review:</strong> {previewReport.summary.review}</div>
                <div className="rounded-lg bg-success-50 p-2 text-success-700"><strong>Compliant:</strong> {previewReport.summary.compliant}</div>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {previewReport.checks.map((check) => (
                <div key={check.id} className="rounded-xl border border-ink-200 p-4">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <p className="font-semibold text-ink-900">{check.name}</p>
                    <span className={`badge text-[10px] ${
                      check.status === 'compliant'
                        ? 'bg-success-50 text-success-700'
                        : check.status === 'non-compliant'
                        ? 'bg-danger-50 text-danger-700'
                        : 'bg-warning-50 text-warning-700'
                    }`}>
                      {check.status.replace('-', ' ')}
                    </span>
                  </div>
                  <div className="mt-3 text-sm text-ink-700 space-y-2">
                    <p><span className="font-semibold text-ink-800">Extracted declaration/value:</span> {check.value}</p>
                    <p><span className="font-semibold text-ink-800">Applicable requirement/rule:</span> {check.requirement}</p>
                    <p><span className="font-semibold text-ink-800">Explanation:</span> {check.explanation}</p>
                    <p><span className="font-semibold text-ink-800">Evidence/source:</span> {check.evidence}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-5 flex flex-col sm:flex-row gap-3 justify-end">
              <button onClick={() => void downloadReportAsPdf(previewReport)} className="btn-primary py-2.5">
                <Save className="w-4 h-4" /> Download PDF
              </button>
              <button onClick={() => setPreviewReport(null)} className="btn-secondary py-2.5">
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
