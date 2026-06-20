"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Circle, Popup, Polyline } from "react-leaflet";
// react-leaflet type mismatches: cast to any for runtime props like `radius`
const AnyCircle: any = Circle as any;
import L from "leaflet";

interface CommandMapProps {
  timelineStep: number; // 0 = Pre-event, 1 = Peak time, 2 = Post-event clearing
  activeLayers: {
    trafficHeatmaps: boolean;
    cityInfrastructure: boolean;
    impactRings: boolean;
    resourceMarkers: boolean;
    cctv: boolean;
    publicTransport: boolean;
  };
  onCctvClick: (camera: { name: string; url: string }) => void;
}

export const CommandMap = ({ timelineStep, activeLayers, onCctvClick }: CommandMapProps) => {
  useEffect(() => {
    const id = "leaflet-css-command";
    if (!document.getElementById(id)) {
      const link = document.createElement("link");
      link.id = id;
      link.rel = "stylesheet";
      link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
      document.head.appendChild(link);
    }
  }, []);

  const center: [number, number] = [12.9716, 77.5946]; // Bangalore center

  // Simulated Infrastructure: Traffic signals
  const signals = [
    { name: "Kanteerava Stadium Junction", lat: 12.9705, lng: 77.5925, status: ["Green", "Red", "Green"][timelineStep] },
    { name: "Hudson Circle", lat: 12.9698, lng: 77.5912, status: ["Green", "Red", "Yellow"][timelineStep] },
    { name: "Richmond Circle", lat: 12.9632, lng: 77.5975, status: ["Green", "Yellow", "Green"][timelineStep] },
    { name: "Queens Junction", lat: 12.9772, lng: 77.5988, status: ["Green", "Red", "Green"][timelineStep] },
  ];

  // Simulated Resources: Personnel and barricades
  const resources = [
    { id: "p1", name: "Officer Ramesh K.", type: "Personnel", lat: 12.9712, lng: 77.5932, task: "Traffic diversion control" },
    { id: "p2", name: "Officer Priya S.", type: "Personnel", lat: 12.9690, lng: 77.5918, task: "Junction manual override" },
    { id: "a1", name: "Barricade Set #4", type: "Asset", lat: 12.9702, lng: 77.5920, task: "Access block to main stadium avenue" },
    { id: "a2", name: "Cones Sector B", type: "Asset", lat: 12.9645, lng: 77.5960, task: "Lane narrowing" },
  ];

  // Simulated CCTV Cameras
  const cctvs = [
    { id: "c1", name: "CCTV - Hudson Circle North", lat: 12.9701, lng: 77.5915, stream: "https://images.unsplash.com/photo-1506012787146-f92b2d7d6d96?q=80&w=300&auto=format&fit=crop" },
    { id: "c2", name: "CCTV - Stadium Gate 2", lat: 12.9719, lng: 77.5940, stream: "https://images.unsplash.com/photo-1473163928189-364b2c4e1135?q=80&w=300&auto=format&fit=crop" },
    { id: "c3", name: "CCTV - Richmond Flyover", lat: 12.9635, lng: 77.5970, stream: "https://images.unsplash.com/photo-1542362567-b07eac790acd?q=80&w=300&auto=format&fit=crop" },
  ];

  // Simulated Public Transit Routes
  const busRoute1: [number, number][] = [
    [12.9780, 77.5910],
    [12.9750, 77.5930],
    [12.9716, 77.5946],
    [12.9680, 77.5955],
    [12.9620, 77.5965]
  ];

  const metroLine: [number, number][] = [
    [12.9710, 77.5800],
    [12.9715, 77.5900],
    [12.9720, 77.6000],
    [12.9725, 77.6100]
  ];

  // Simulated Heatmap Points (varying intensity by timeline step)
  const heatmapPoints = [
    // Pre-event
    [
      { lat: 12.9716, lng: 77.5946, score: 0.6, count: 12 },
      { lat: 12.9705, lng: 77.5925, score: 0.4, count: 6 },
      { lat: 12.9698, lng: 77.5912, score: 0.3, count: 4 },
    ],
    // Peak Time
    [
      { lat: 12.9716, lng: 77.5946, score: 0.95, count: 42 },
      { lat: 12.9705, lng: 77.5925, score: 0.85, count: 28 },
      { lat: 12.9698, lng: 77.5912, score: 0.8, count: 22 },
      { lat: 12.9772, lng: 77.5988, score: 0.65, count: 15 },
      { lat: 12.9632, lng: 77.5975, score: 0.55, count: 11 },
    ],
    // Post-event Clearing
    [
      { lat: 12.9716, lng: 77.5946, score: 0.45, count: 9 },
      { lat: 12.9705, lng: 77.5925, score: 0.5, count: 14 },
      { lat: 12.9698, lng: 77.5912, score: 0.4, count: 8 },
    ],
  ][timelineStep];

  // Custom Icon Helpers using static colors instead of SVG files to be 100% robust
  const createDivIcon = (html: string, className = "") => {
    return typeof window !== "undefined"
      ? L.divIcon({
          html,
          className: `custom-div-icon ${className}`,
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        })
      : null;
  };

  const getSignalIcon = (status: string) => {
    const color = status === "Red" ? "#EF4444" : status === "Yellow" ? "#F59E0B" : "#10B981";
    return createDivIcon(`
      <div style="background-color: ${color}; width: 16px; height: 16px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); animation: pulse 2s infinite;"></div>
    `) as any;
  };

  const getResourceIcon = (type: string) => {
    const bgColor = type === "Personnel" ? "#3B82F6" : "#F97316";
    const innerHtml = type === "Personnel" ? "👮" : "🚧";
    return createDivIcon(`
      <div style="background-color: ${bgColor}; font-size: 14px; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
        ${innerHtml}
      </div>
    `) as any;
  };

  const getCctvIcon = () => {
    return createDivIcon(`
      <div style="background-color: #7C3AED; font-size: 12px; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
        🎥
      </div>
    `) as any;
  };

  // Color mappings
  const heatColor = (score: number) => {
    if (score > 0.8) return "#EF4444"; // Red
    if (score > 0.5) return "#F97316"; // Orange
    if (score > 0.3) return "#EAB308"; // Yellow
    return "#10B981"; // Green
  };

  const ringColor = ["#EAB308", "#EF4444", "#3B82F6"][timelineStep];
  const ringRadius = [150, 300, 180][timelineStep];

  return (
    <div className="h-full w-full">
      {/* @ts-ignore */}
      <MapContainer center={center} zoom={14} style={{ height: "100%", width: "100%" }} zoomControl={false}>
        <TileLayer
          {...({
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
          } as any)}
        />

        {/* 1. Public Transport Routes Layer */}
        {activeLayers.publicTransport && (
          <>
            <Polyline
              positions={busRoute1}
              pathOptions={{ color: "#6366F1", weight: 4, dashArray: "5, 10" }}
            />
            <Polyline positions={metroLine} pathOptions={{ color: "#10B981", weight: 5 }} />
          </>
        )}

        {/* 2. Traffic Heatmaps Layer */}
        {activeLayers.trafficHeatmaps &&
          heatmapPoints.map((point, idx) => (
            <AnyCircle
              key={`heat-${idx}`}
              center={[point.lat, point.lng]}
              radius={15 + point.score * 25}
              pathOptions={{
                color: heatColor(point.score),
                fillColor: heatColor(point.score),
                fillOpacity: 0.35 + point.score * 0.25,
                stroke: false,
              }}
              >
              <Popup>
                <div className="font-['Outfit']">
                  <div className="font-semibold text-stone-800">Congestion Heatspot</div>
                  <div className="text-xs text-stone-500">Predicted Congestion Index: {(point.score * 100).toFixed(0)}%</div>
                  <div className="text-xs text-stone-500">Live Traffic Flow Rate: {point.count} vehicles/min</div>
                </div>
              </Popup>
            </AnyCircle>
          ))}

        {/* 3. Event Impact Rings Layer */}
        {activeLayers.impactRings && (
          <AnyCircle
            center={center}
            pathOptions={{
              color: ringColor,
              fillColor: ringColor,
              fillOpacity: timelineStep === 1 ? 0.15 : 0.08,
              weight: timelineStep === 1 ? 3 : 2,
              dashArray: timelineStep === 1 ? "6, 6" : undefined,
            }}
            radius={ringRadius / 2}
          >
            <Popup>
              <div className="font-['Outfit']">
                <div className="font-semibold text-stone-800">Kanteerava Stadium Concert</div>
                <div className="text-xs text-red-500 font-medium">Impact Ring: {ringRadius}m Radius</div>
                <div className="text-xs text-stone-500">
                  {timelineStep === 0 && "Pre-Event: Gridlock Risk building up."}
                  {timelineStep === 1 && "Event Peak: Heavy pedestrian spillover, major street blocks."}
                  {timelineStep === 2 && "Post-Event: Crowd dispersing, lanes gradually recovering."}
                </div>
              </div>
            </Popup>
          </AnyCircle>
        )}

        {/* 4. City Infrastructure (Traffic Signals) Layer */}
        {activeLayers.cityInfrastructure &&
          signals.map((sig, idx) => {
            const icon = getSignalIcon(sig.status);
            if (!icon) return null;
            const { Marker: LMarker } = require("react-leaflet");
            return (
              <LMarker key={`sig-${idx}`} position={[sig.lat, sig.lng]} icon={icon}>
                <Popup>
                  <div className="font-['Outfit']">
                    <div className="font-semibold text-stone-800">{sig.name}</div>
                    <div className="text-xs flex items-center gap-1.5 mt-1">
                      Signal Status:
                      <span
                        className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-white"
                        style={{
                          backgroundColor:
                            sig.status === "Red" ? "#EF4444" : sig.status === "Yellow" ? "#F59E0B" : "#10B981",
                        }}
                      >
                        {sig.status} (Adaptive)
                      </span>
                    </div>
                  </div>
                </Popup>
              </LMarker>
            );
          })}

        {/* 5. Resource Markers Layer */}
        {activeLayers.resourceMarkers &&
          resources.map((res, idx) => {
            const icon = getResourceIcon(res.type);
            if (!icon) return null;
            const { Marker: LMarker } = require("react-leaflet");
            return (
              <LMarker key={`res-${idx}`} position={[res.lat, res.lng]} icon={icon}>
                <Popup>
                  <div className="font-['Outfit']">
                    <div className="font-semibold text-stone-800">{res.name}</div>
                    <div className="text-xs text-stone-500">Category: {res.type}</div>
                    <div className="text-xs text-stone-600 italic mt-1 font-medium">Assigned: {res.task}</div>
                  </div>
                </Popup>
              </LMarker>
            );
          })}

        {/* 6. CCTV Cameras Layer */}
        {activeLayers.cctv &&
          cctvs.map((cam, idx) => {
            const icon = getCctvIcon();
            if (!icon) return null;
            const { Marker: LMarker } = require("react-leaflet");
            return (
              <LMarker
                key={`cam-${idx}`}
                position={[cam.lat, cam.lng]}
                icon={icon}
                eventHandlers={{
                  click: () => onCctvClick({ name: cam.name, url: cam.stream }),
                }}
              >
                <Popup>
                  <div className="font-['Outfit'] text-center">
                    <div className="font-semibold text-stone-800">{cam.name}</div>
                    <div className="text-[10px] text-purple-600 font-semibold mt-1">Click to Stream Live Feed</div>
                  </div>
                </Popup>
              </LMarker>
            );
          })}
      </MapContainer>
    </div>
  );
};
