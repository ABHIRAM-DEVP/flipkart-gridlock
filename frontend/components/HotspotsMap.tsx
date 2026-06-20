"use client";

import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, LayersControl, LayerGroup, Marker } from "react-leaflet";
// relax react-leaflet typings where necessary
const AnyCircleMarker: any = CircleMarker as any;
import L from 'leaflet';
// Load Leaflet CSS only on the client to avoid SSR errors

export const HotspotsMap = ({ hotspots: inputHotspots }: { hotspots?: any[] }) => {
  const [events, setEvents] = useState<any[]>([]);
  const [resources, setResources] = useState<any[]>([]);
  const [mounted, setMounted] = useState(false);
  const mapIdRef = React.useRef(`hotspots-map-${Date.now()}-${Math.floor(Math.random()*10000)}`);
  const renderedRef = React.useRef(false);
  const hotspots = inputHotspots ?? [];

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
  const hasCoords = lats.length > 0 && lngs.length > 0;
  const minLat = hasCoords ? Math.min(...lats) : 28.7041;
  const maxLat = hasCoords ? Math.max(...lats) : 28.7041;
  const minLng = hasCoords ? Math.min(...lngs) : 77.1025;
  const maxLng = hasCoords ? Math.max(...lngs) : 77.1025;
  const spanLat = Math.max(maxLat - minLat, 1e-6);
  const spanLng = Math.max(maxLng - minLng, 1e-6);
  const maxScore = Math.max(...normalized.map((h) => h.score), 1);

  // compute map center
  const centerLat = (minLat + maxLat) / 2;
  const centerLng = (minLng + maxLng) / 2;

  useEffect(() => {
    const id = 'leaflet-css';
    if (!document.getElementById(id)) {
      const link = document.createElement('link');
      link.id = id;
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }
    // fetch events and resources for overlays
    (async () => {
      try {
        const r = await fetch('/api/events');
        const d = await r.json();
        setEvents(d.events || []);
      } catch (e) {
        setEvents([]);
      }
      try {
        const r2 = await fetch('/api/resources');
        const d2 = await r2.json();
        setResources(d2.resources || []);
      } catch (e) {
        setResources([{ id: 'r1', lat: 28.7041, lng: 77.1025, type: 'personnel', name: 'Team A' }]);
      }
    })();
    // ensure map only renders on client after effects to avoid double-init
    // remove any existing container with the same id to avoid Leaflet re-init errors (HMR/dev)
    try {
      const existing = document.getElementById(mapIdRef.current);
      if (existing && existing.parentElement) existing.parentElement.removeChild(existing);
    } catch (e) {
      /* ignore */
    }
    setMounted(true);
  }, []);

  return (
    <div className="space-y-6">
      <div className="relative overflow-hidden rounded-3xl border border-stone-100 p-4 min-h-[320px]">
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

        <div className="h-[360px] rounded-[1.6rem] overflow-hidden">
          {/* TS types mismatch in this workspace; cast to any to satisfy build */}
          {/* Render MapContainer only after client mount to avoid double init */}
          {mounted && !renderedRef.current && (
            // prevent multiple initializations during HMR: render MapContainer only once per session
            // @ts-ignore
            <MapContainer center={[centerLat, centerLng] as any} zoom={12} style={{ height: "100%", width: "100%" }}>
              <LayersControl>
              <LayersControl.BaseLayer checked name="OpenStreetMap">
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              </LayersControl.BaseLayer>

              <LayersControl.Overlay name="Traffic Heatmap">
                <LayerGroup>
                  {normalized.map((h, idx) => (
                    <AnyCircleMarker
                      key={idx}
                      center={[h.lat, h.lng] as any}
                      radius={(6 + (h.score / maxScore) * 18) as any}
                      pathOptions={{ color: heatColor(h.score / maxScore), fillOpacity: 0.6 } as any}
                    >
                      <Popup>
                        <div>
                          <div className="font-medium">{h.count} events</div>
                          <div className="text-sm">Avg duration: {h.duration ? `${h.duration.toFixed(1)} mins` : 'N/A'}</div>
                          <div className="text-sm">Score: {h.score.toFixed(1)}</div>
                        </div>
                      </Popup>
                    </AnyCircleMarker>
                  ))}
                </LayerGroup>
              </LayersControl.Overlay>

              <LayersControl.Overlay name="Event Impact Rings">
                <LayerGroup>
                  {events.map((ev, i) => (
                    <AnyCircleMarker key={`ev-${i}`} center={[ev.lat, ev.lng] as any} radius={Math.max(20, (ev.impact || 0) * 30)} pathOptions={{ color: impactColor(ev.impact || 0), weight: 2, fill: false } as any}>
                      <Popup>
                        <div>
                          <strong>{ev.title || 'Event'}</strong>
                          <div>Projected Load: {ev.impact}</div>
                        </div>
                      </Popup>
                    </AnyCircleMarker>
                  ))}
                </LayerGroup>
              </LayersControl.Overlay>

              <LayersControl.Overlay name="Resources">
                <LayerGroup>
                  {resources.map((res) => (
                    // @ts-ignore
                    <Marker key={res.id} position={[res.lat, res.lng] as any} icon={resourceIcon(res.type)}>
                      <Popup>
                        <div>
                          <strong>{res.name}</strong>
                          <div>Type: {res.type}</div>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </LayerGroup>
              </LayersControl.Overlay>
            </LayersControl>
            </MapContainer>
          )}
          {mounted && (() => { renderedRef.current = true; return null; })()}
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

  function heatColor(t: number) {
    const v = Math.max(0, Math.min(1, t));
    const r = Math.floor(255 * v);
    const g = Math.floor(200 * (1 - v));
    return `rgb(${r},${g},0)`;
  }

  function impactColor(v: number) {
    if (v > 0.75) return 'red';
    if (v > 0.4) return 'orange';
    return 'green';
  }

  function resourceIcon(type: string) {
    const size = [28, 28] as [number, number];
    const url = type === 'personnel' ? '/icons/person.svg' : '/icons/marker.svg';
    return L.icon({ iconUrl: url, iconSize: size, iconAnchor: [14, 28] });
  }
