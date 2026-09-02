import { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, ScanLine } from 'lucide-react';

const steps = [
  'Image uploaded',
  'Label text extracted',
  'Product information extracted',
  'Mandatory declarations checked',
  'Compliance rules analyzed',
  'Report generated',
];

export function Analysis({ image, onDone }: { image: string; onDone: () => void }) {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (current >= steps.length) {
      const t = setTimeout(onDone, 600);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setCurrent((c) => c + 1), 850);
    return () => clearTimeout(t);
  }, [current, onDone]);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-900">Analyzing product…</h1>
        <p className="text-ink-500 mt-1 text-sm sm:text-base">
          NIRIKSHA is running a compliance check against Legal Metrology requirements.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-4">
          <div className="rounded-xl overflow-hidden bg-ink-100 aspect-square relative">
            <img src={image} alt="Analyzing" className="w-full h-full object-cover" />
            <div className="absolute inset-0 ring-2 ring-brand-400/60 ring-inset rounded-xl pointer-events-none" />
            <div className="absolute top-3 left-3 badge bg-ink-950/70 text-white backdrop-blur">
              <ScanLine className="w-3.5 h-3.5" /> Scanning
            </div>
          </div>
        </div>

        <div className="card p-5 sm:p-6">
          <ol className="space-y-4">
            {steps.map((label, i) => {
              const done = i < current;
              const active = i === current;
              return (
                <li key={label} className="flex items-center gap-3">
                  <div className="shrink-0">
                    {done ? (
                      <CheckCircle2 className="w-5 h-5 text-success-500 animate-step-pop" />
                    ) : active ? (
                      <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border-2 border-ink-200" />
                    )}
                  </div>
                  <span
                    className={`text-sm transition-colors ${
                      done
                        ? 'text-ink-800 font-medium'
                        : active
                        ? 'text-brand-700 font-semibold'
                        : 'text-ink-400'
                    }`}
                  >
                    {label}
                  </span>
                </li>
              );
            })}
          </ol>

          <div className="mt-6 pt-5 border-t border-ink-100">
            <div className="flex items-center justify-between text-xs text-ink-500 mb-2">
              <span>Step {Math.min(current + 1, steps.length)} of {steps.length}</span>
              <span>{Math.round((Math.min(current, steps.length) / steps.length) * 100)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-ink-200 overflow-hidden">
              <div
                className="h-full bg-brand-500 transition-all duration-500"
                style={{ width: `${(Math.min(current, steps.length) / steps.length) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
