import { MapPin, AlertTriangle, Navigation } from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader } from '@/components/ui';
import { violationMapData } from '@/data';

export function ViolationMap() {
  const { setPage } = useApp();
  const maxCount = Math.max(...violationMapData.map((z) => z.count));
  const total = violationMapData.reduce((a, z) => a + z.count, 0);

  return (
    <div>
      <PageHeader
        title="Violation Map"
        subtitle="Geographic distribution of detected violations across the zone."
      />

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Map placeholder */}
        <div className="card p-5 lg:col-span-2">
          <div className="relative rounded-xl overflow-hidden bg-brand-50 border border-ink-200 aspect-[16/10]">
            {/* Stylized map */}
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 400 250" preserveAspectRatio="none">
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#dae6ff" strokeWidth="1" />
                </pattern>
              </defs>
              <rect width="400" height="250" fill="url(#grid)" />
              <path
                d="M 20 180 Q 100 120 180 140 T 380 80"
                fill="none"
                stroke="#bcd2ff"
                strokeWidth="3"
              />
              <path
                d="M 60 40 Q 120 100 200 80 T 360 200"
                fill="none"
                stroke="#dae6ff"
                strokeWidth="2"
              />
            </svg>
            {violationMapData.map((z, i) => {
              const left = 10 + (i * 14) + (i % 2) * 6;
              const top = 15 + (i * 11) + (i % 3) * 5;
              const size = 18 + (z.count / maxCount) * 26;
              return (
                <div
                  key={z.zone}
                  className="absolute -translate-x-1/2 -translate-y-1/2 group"
                  style={{ left: `${left}%`, top: `${top}%` }}
                >
                  <div
                    className="rounded-full bg-danger-500/30 border-2 border-danger-500 flex items-center justify-center text-danger-700 font-bold text-xs hover:scale-110 transition-transform cursor-pointer"
                    style={{ width: `${size}px`, height: `${size}px` }}
                  >
                    {z.count}
                  </div>
                  <div className="absolute left-1/2 -translate-x-1/2 -top-8 opacity-0 group-hover:opacity-100 transition-opacity bg-ink-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap pointer-events-none">
                    {z.zone}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-4 mt-4 text-xs text-ink-500">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-danger-500/30 border-2 border-danger-500" />
              Violation hotspot
            </span>
            <span className="flex items-center gap-1.5">
              <Navigation className="w-3.5 h-3.5" /> {total} total violations
            </span>
          </div>
        </div>

        {/* Zone list */}
        <div className="card p-5">
          <h3 className="font-semibold text-ink-900 mb-4">Zones by Violations</h3>
          <div className="space-y-2">
            {violationMapData
              .slice()
              .sort((a, b) => b.count - a.count)
              .map((z, i) => (
                <button
                  key={z.zone}
                  onClick={() => setPage('reports')}
                  className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-ink-50 transition-colors text-left"
                >
                  <span className="w-6 h-6 rounded-lg bg-ink-100 text-ink-500 flex items-center justify-center text-xs font-bold">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-ink-800">{z.zone}</p>
                    <p className="text-xs text-ink-500 flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> {z.lat}, {z.lng}
                    </p>
                  </div>
                  <span className="badge bg-danger-50 text-danger-700">
                    <AlertTriangle className="w-3 h-3" /> {z.count}
                  </span>
                </button>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
