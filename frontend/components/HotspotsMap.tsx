import React from 'react';

export const HotspotsMap = ({ hotspots }: { hotspots: any[] }) => {
  if (!hotspots || hotspots.length === 0) {
    return <div className="text-[var(--text-muted)] py-4">No hotspots identified.</div>;
  }

  const normalized = hotspots
    .map((h) => ({
      ...h,
      lat: Number(h.centroid_latitude ?? h.latitude ?? h.lat ?? 0),
      lng: Number(h.centroid_longitude ?? h.longitude ?? h.lng ?? 0),
      score: Number(h.hotspot_score ?? h.score ?? 0),
      count: Number(h.count ?? h.cluster_size ?? 0),
      duration: Number(h.avg_duration_min ?? h.avg_duration ?? 0),
    }))
    .filter((h) => Number.isFinite(h.lat) && Number.isFinite(h.lng));

  const lats = normalized.map((h) => h.lat);
  const lngs = normalized.map((h) => h.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const spanLat = Math.max(maxLat - minLat, 1e-6);
  const spanLng = Math.max(maxLng - minLng, 1e-6);
  const maxScore = Math.max(...normalized.map((h) => h.score), 1);

  return (
    <div className="space-y-6">
      <div className="relative overflow-hidden rounded-3xl border border-stone-100 bg-[linear-gradient(135deg,rgba(255,183,178,0.35),rgba(239,237,244,0.75)_55%,rgba(232,239,232,0.85))] p-4 min-h-[320px]">
        <div className="absolute inset-0 opacity-40 bg-[radial-gradient(circle_at_20%_20%,rgba(255,183,178,0.8),transparent_24%),radial-gradient(circle_at_75%_30%,rgba(255,154,140,0.6),transparent_22%),radial-gradient(circle_at_45%_80%,rgba(34,197,94,0.35),transparent_18%)]" />
        <div className="relative flex items-center justify-between mb-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-[var(--text-muted)]">Congestion heat map</p>
            <h3 className="text-xl font-semibold text-[var(--text-main)]">DBSCAN hotspot density</h3>
          </div>
          <div className="text-right text-xs text-[var(--text-muted)]">
            <div>{normalized.length} clusters plotted</div>
            <div>Intensity scales with hotspot score</div>
          </div>
        </div>
        <div className="relative h-[240px] rounded-[1.6rem] border border-white/60 bg-white/50 overflow-hidden backdrop-blur-sm">
          <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.03)_1px,transparent_1px)] bg-[size:36px_36px]" />
          {normalized.map((h, index) => {
            const left = ((h.lng - minLng) / spanLng) * 100;
            const top = 100 - ((h.lat - minLat) / spanLat) * 100;
            const size = 18 + (h.score / maxScore) * 32;
            const opacity = 0.45 + (h.score / maxScore) * 0.5;
            return (
              <div
                key={`${h.lat}-${h.lng}-${index}`}
                title={`${h.count} events | score ${h.score.toFixed(1)}`}
                className="absolute rounded-full border border-white shadow-[0_0_24px_rgba(239,68,68,0.28)]"
                style={{
                  left: `${Math.min(95, Math.max(3, left))}%`,
                  top: `${Math.min(95, Math.max(5, top))}%`,
                  width: `${size}px`,
                  height: `${size}px`,
                  transform: 'translate(-50%, -50%)',
                  background: `radial-gradient(circle at 30% 30%, rgba(255,255,255,0.95), rgba(255,183,178,${opacity}) 45%, rgba(239,68,68,${opacity}) 100%)`,
                }}
              />
            );
          })}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-stone-100 text-[var(--text-muted)] text-sm">
              <th className="pb-3 font-medium px-4">Location (Lat, Lng)</th>
              <th className="pb-3 font-medium px-4">Cluster Size</th>
              <th className="pb-3 font-medium px-4">Avg Duration</th>
              <th className="pb-3 font-medium px-4">Heat Score</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {normalized.map((h, i) => (
              <tr key={i} className="border-b border-stone-50 hover:bg-stone-50/50 transition-colors">
                <td className="py-4 px-4 font-medium">
                  {h.lat.toFixed(4)}, {h.lng.toFixed(4)}
                </td>
                <td className="py-4 px-4">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[var(--accent-lavender)] text-stone-700">
                    {h.count} events
                  </span>
                </td>
                <td className="py-4 px-4 text-[var(--text-muted)]">
                  {h.duration ? `${h.duration.toFixed(1)} mins` : 'N/A'}
                </td>
                <td className="py-4 px-4 font-semibold text-[var(--text-main)]">
                  {h.score.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
