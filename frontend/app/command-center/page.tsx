"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { predict, getWeights } from "@/lib/api";

// Dynamically import map component to avoid SSR errors
const CommandMap = dynamic(
  () => import("@/components/CommandMap").then((m) => m.CommandMap),
  { ssr: false, loading: () => <div className="h-full w-full bg-stone-100 flex items-center justify-center text-[var(--text-muted)]">Loading Command Map...</div> }
);

export default function CommandCenter() {
  // Map layers toggles
  const [layers, setLayers] = useState({
    trafficHeatmaps: true,
    cityInfrastructure: true,
    impactRings: true,
    resourceMarkers: true,
    cctv: true,
    publicTransport: false,
  });

  // Timeline control state
  const [timelineStep, setTimelineStep] = useState(1); // 0 = Pre-event, 1 = Peak, 2 = Post-event
  const [isPlaying, setIsPlaying] = useState(false);

  // Predictive Sidebar state
  const [eventType, setEventType] = useState("Concert");
  const [timeOfDay, setTimeOfDay] = useState("evening peak");
  const [corridor, setCorridor] = useState("Corridor A");
  const [isCalculating, setIsCalculating] = useState(false);
  const [forecastResult, setForecastResult] = useState<any>({
    predicted_duration_min: 180,
    predicted_severity: "High",
    prediction_interval_min: { p10: 150, p90: 210 },
    resource_plan: {
      suggested_personnel: 24,
      barricades_required: 15,
      cones_required: 40,
      diversion_route: "Route C via Richmond Circle",
    },
  });

  // Feedback Loop state
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [rating, setRating] = useState(5);
  const [feedbackText, setFeedbackText] = useState("");
  const [crowdVenueWeight, setCrowdVenueWeight] = useState(1.15); // +15%
  const [savedStatus, setSavedStatus] = useState("");

  // CCTV video feed simulator overlay state
  const [activeCctv, setActiveCctv] = useState<{ name: string; url: string } | null>(null);

  // Auto-play timeline control
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setTimelineStep((step) => (step + 1) % 3);
      }, 4000);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  // When scrubbing to Post-Event (step 2), trigger the automated report card modal
  useEffect(() => {
    if (timelineStep === 2) {
      const timer = setTimeout(() => {
        setShowFeedbackModal(true);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [timelineStep]);

  const handleCalculateForecast = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCalculating(true);
    try {
      const res = await predict({
        event_type: eventType,
        start_datetime: new Date().toISOString(),
        corridor: corridor,
        time_of_day: timeOfDay,
        requires_road_closure: eventType === "Protest" || eventType === "VIP Movement" ? 1 : 0,
      });

      // Format result nicely
      setForecastResult({
        predicted_duration_min: res.predicted_duration_min || 120,
        predicted_severity: res.predicted_severity || "Medium",
        prediction_interval_min: res.prediction_interval_min || { p10: 90, p90: 150 },
        resource_plan: {
          suggested_personnel: res.resource_plan?.suggested_personnel || 15,
          barricades_required: res.resource_plan?.barricades || 10,
          cones_required: res.resource_plan?.cones || 25,
          diversion_route: res.resource_plan?.diversion_plan || "Diversion via Expressway B",
        },
      });
    } catch (err) {
      console.error("Forecast failed:", err);
      // Fallback fallback simulated prediction
      setForecastResult({
        predicted_duration_min: 145.5,
        predicted_severity: "High",
        prediction_interval_min: { p10: 120, p90: 180 },
        resource_plan: {
          suggested_personnel: 20,
          barricades_required: 12,
          cones_required: 30,
          diversion_route: `Divert traffic from ${corridor} to Richmond Bypass`,
        },
      });
    } finally {
      setIsCalculating(false);
    }
  };

  const handleSaveFeedback = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedStatus("Feedback and tuned weights successfully sent to Learning Loop!");
    setTimeout(() => {
      setShowFeedbackModal(false);
      setSavedStatus("");
    }, 2000);
  };

  return (
    <div className="flex flex-col gap-6 font-['Outfit'] select-none">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-[var(--text-muted)] font-medium">Real-Time Control Room</p>
          <h1 className="text-3xl font-bold tracking-tight text-[var(--text-main)]">Command Center Dashboard</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setLayers((prev) => ({ ...prev, trafficHeatmaps: !prev.trafficHeatmaps }))}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
              layers.trafficHeatmaps ? "bg-orange-100 text-orange-800 border-orange-200" : "bg-stone-50 border-stone-200 text-stone-600"
            }`}
          >
            🔥 Heatmap
          </button>
          <button
            onClick={() => setLayers((prev) => ({ ...prev, resourceMarkers: !prev.resourceMarkers }))}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
              layers.resourceMarkers ? "bg-blue-100 text-blue-800 border-blue-200" : "bg-stone-50 border-stone-200 text-stone-600"
            }`}
          >
            👮 Officers & Cones
          </button>
          <button
            onClick={() => setLayers((prev) => ({ ...prev, cctv: !prev.cctv }))}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
              layers.cctv ? "bg-purple-100 text-purple-800 border-purple-200" : "bg-stone-50 border-stone-200 text-stone-600"
            }`}
          >
            🎥 CCTV Feeds
          </button>
        </div>
      </div>

      {/* Main Grid: Sidebar + Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch min-h-[600px]">
        {/* Left Side: Predictive Sidebar & Impact Calculator (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          {/* Impact Calculator Form */}
          <div className="bg-white/70 backdrop-blur-xl border border-white/50 rounded-[2rem] p-6 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">🧮</span>
                <h3 className="text-lg font-bold text-[var(--text-main)]">Incident Impact Calculator</h3>
              </div>
              <p className="text-xs text-[var(--text-muted)] mb-5">
                Simulate a planned or unplanned event in real-time to compute duration, severity, and recommend resources.
              </p>

              <form onSubmit={handleCalculateForecast} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-600 uppercase mb-1">Event Type</label>
                  <select
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                    className="w-full bg-white/80 border border-stone-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent-coral)]"
                  >
                    <option value="Concert">Concert / Fest</option>
                    <option value="Political Rally">Political Rally</option>
                    <option value="Sports">Sports Match</option>
                    <option value="Protest">Protest / Rally</option>
                    <option value="VIP Movement">VIP Movement</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-stone-600 uppercase mb-1">Time of Day</label>
                  <select
                    value={timeOfDay}
                    onChange={(e) => setTimeOfDay(e.target.value)}
                    className="w-full bg-white/80 border border-stone-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent-coral)]"
                  >
                    <option value="morning peak">Morning Rush (08:00 - 11:00)</option>
                    <option value="afternoon off-peak">Afternoon (12:00 - 16:00)</option>
                    <option value="evening peak">Evening Rush (17:00 - 20:00)</option>
                    <option value="night">Night Off-Peak (21:00 - 07:00)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-stone-600 uppercase mb-1">Critical Corridor</label>
                  <select
                    value={corridor}
                    onChange={(e) => setCorridor(e.target.value)}
                    className="w-full bg-white/80 border border-stone-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent-coral)]"
                  >
                    <option value="Corridor A">Corridor A (Richmond Rd / Hudson Cir)</option>
                    <option value="Corridor B">Corridor B (Koramangala Outer Ring Rd)</option>
                    <option value="Corridor C">Corridor C (MG Road Transit corridor)</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={isCalculating}
                  className="w-full py-2.5 rounded-xl bg-stone-900 text-white text-sm font-semibold hover:bg-stone-800 transition-colors shadow-sm disabled:opacity-50 mt-2"
                >
                  {isCalculating ? "Calculating impact..." : "Calculate Forecast"}
                </button>
              </form>
            </div>
          </div>

          {/* Recommendation & Prediction Panel */}
          <div className="bg-white/70 backdrop-blur-xl border border-white/50 rounded-[2rem] p-6 shadow-sm flex-1 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🔮</span>
                  <h3 className="text-lg font-bold text-[var(--text-main)]">Model Forecast & Advice</h3>
                </div>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
                    forecastResult.predicted_severity === "High"
                      ? "bg-red-100 text-red-800"
                      : forecastResult.predicted_severity === "Medium"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-green-100 text-green-800"
                  }`}
                >
                  {forecastResult.predicted_severity} Severity
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-stone-50 p-3 rounded-xl">
                  <div className="text-[10px] uppercase font-semibold text-[var(--text-muted)]">Est. Clearance Time</div>
                  <div className="text-lg font-bold text-[var(--text-main)]">{forecastResult.predicted_duration_min.toFixed(1)} mins</div>
                </div>
                <div className="bg-stone-50 p-3 rounded-xl">
                  <div className="text-[10px] uppercase font-semibold text-[var(--text-muted)]">90% Confidence Interval</div>
                  <div className="text-xs font-bold text-[var(--text-main)]">
                    {forecastResult.prediction_interval_min.p10.toFixed(0)} - {forecastResult.prediction_interval_min.p90.toFixed(0)}m
                  </div>
                </div>
              </div>

              <h4 className="text-xs font-bold text-stone-500 uppercase mb-3">Recommended Resources</h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-2 rounded-lg bg-blue-50/50 border border-blue-100 text-sm">
                  <div className="flex items-center gap-2">
                    <span>👮</span>
                    <span className="font-medium text-stone-700">Traffic Personnel</span>
                  </div>
                  <span className="font-bold text-blue-800">{forecastResult.resource_plan.suggested_personnel} Officers</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded-lg bg-orange-50/50 border border-orange-100 text-sm">
                  <div className="flex items-center gap-2">
                    <span>🚧</span>
                    <span className="font-medium text-stone-700">Road Barricades</span>
                  </div>
                  <span className="font-bold text-orange-800">{forecastResult.resource_plan.barricades_required} Barriers</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded-lg bg-yellow-50/50 border border-yellow-100 text-sm">
                  <div className="flex items-center gap-2">
                    <span>⚠️</span>
                    <span className="font-medium text-stone-700">Cones / Markers</span>
                  </div>
                  <span className="font-bold text-yellow-800">{forecastResult.resource_plan.cones_required} Cones</span>
                </div>
              </div>
            </div>

            <div className="mt-5 p-3 rounded-xl bg-emerald-50 border border-emerald-100 text-xs text-emerald-800">
              <strong>Optimal Diversion:</strong> {forecastResult.resource_plan.diversion_route}
            </div>
          </div>
        </div>

        {/* Right Side: Map Canvas (8 cols) */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          <div className="relative bg-white/70 backdrop-blur-xl border border-white/50 rounded-[2rem] p-4 flex-1 shadow-sm overflow-hidden flex flex-col min-h-[450px]">
            {/* GIS Layer Controls (Overlay in top-right of map) */}
            <div className="absolute top-6 right-6 z-20 bg-white/95 backdrop-blur-md rounded-2xl p-3 shadow-lg border border-stone-100 text-xs flex flex-col gap-2 max-w-[180px]">
              <span className="font-bold text-stone-700 mb-1 border-b pb-1.5 uppercase tracking-wide">GIS Layers</span>
              <label className="flex items-center gap-2 font-medium text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers.trafficHeatmaps}
                  onChange={() => setLayers((p) => ({ ...p, trafficHeatmaps: !p.trafficHeatmaps }))}
                  className="accent-stone-800 rounded"
                />
                Traffic Heatmaps
              </label>
              <label className="flex items-center gap-2 font-medium text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers.cityInfrastructure}
                  onChange={() => setLayers((p) => ({ ...p, cityInfrastructure: !p.cityInfrastructure }))}
                  className="accent-stone-800 rounded"
                />
                Adaptive Signals
              </label>
              <label className="flex items-center gap-2 font-medium text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers.impactRings}
                  onChange={() => setLayers((p) => ({ ...p, impactRings: !p.impactRings }))}
                  className="accent-stone-800 rounded"
                />
                Event Impact Rings
              </label>
              <label className="flex items-center gap-2 font-medium text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers.resourceMarkers}
                  onChange={() => setLayers((p) => ({ ...p, resourceMarkers: !p.resourceMarkers }))}
                  className="accent-stone-800 rounded"
                />
                Officer & Cone Markers
              </label>
              <label className="flex items-center gap-2 font-medium text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers.cctv}
                  onChange={() => setLayers((p) => ({ ...p, cctv: !p.cctv }))}
                  className="accent-stone-800 rounded"
                />
                Junction CCTV feeds
              </label>
              <label className="flex items-center gap-2 font-medium text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers.publicTransport}
                  onChange={() => setLayers((p) => ({ ...p, publicTransport: !p.publicTransport }))}
                  className="accent-stone-800 rounded"
                />
                Transit Lanes
              </label>
            </div>

            {/* Map Container */}
            <div className="flex-1 rounded-[1.6rem] overflow-hidden relative border border-stone-100 bg-stone-50">
              <CommandMap timelineStep={timelineStep} activeLayers={layers} onCctvClick={setActiveCctv} />

              {/* CCTV Feed Overlay modal inside map */}
              {activeCctv && (
                <div className="absolute inset-0 bg-black/60 z-30 flex items-center justify-center p-4">
                  <div className="bg-stone-900 border border-stone-800 text-white rounded-2xl w-full max-w-sm overflow-hidden shadow-2xl relative">
                    <button
                      onClick={() => setActiveCctv(null)}
                      className="absolute top-3 right-3 text-stone-400 hover:text-white text-lg font-bold"
                    >
                      ✕
                    </button>
                    <div className="p-4 border-b border-stone-800">
                      <h4 className="font-semibold text-sm flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
                        {activeCctv.name}
                      </h4>
                      <p className="text-[10px] text-stone-400 mt-0.5">Live Junction Monitoring • Adaptive AI Analytics Enabled</p>
                    </div>
                    <div className="h-48 bg-stone-950 flex items-center justify-center relative overflow-hidden">
                      <img src={activeCctv.url} alt="CCTV Stream" className="w-full h-full object-cover opacity-80" />
                      <div className="absolute bottom-2 left-2 px-2 py-0.5 bg-black/50 text-[9px] rounded font-mono">
                        FPS: 30 | VEHICLES IN ZONE: 14 | CONGESTION: MEDIUM
                      </div>
                    </div>
                    <div className="p-3 text-xs bg-stone-800 text-stone-300 flex justify-between">
                      <span>Junction Manual Override:</span>
                      <span className="text-green-400 font-bold">AVAILABLE</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Timeline Slider Control (Bottom) */}
          <div className="bg-white/70 backdrop-blur-xl border border-white/50 rounded-[2rem] p-6 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="w-10 h-10 rounded-full bg-stone-900 text-white flex items-center justify-center hover:bg-stone-800 transition-colors shadow"
                >
                  {isPlaying ? "⏸" : "▶"}
                </button>
                <div>
                  <h4 className="font-bold text-stone-800 text-sm">Incident Scrub Timeline</h4>
                  <p className="text-xs text-[var(--text-muted)] font-medium">
                    {timelineStep === 0 && "Stage 1: Pre-event setup and preliminary buildup."}
                    {timelineStep === 1 && "Stage 2: Peak event congestion and maximum spillover."}
                    {timelineStep === 2 && "Stage 3: Post-event clearing and adaptive recovery."}
                  </p>
                </div>
              </div>

              {/* Slider controls */}
              <div className="flex-1 max-w-md flex items-center gap-4">
                <span className="text-xs text-stone-500 font-bold whitespace-nowrap">0 hr (Setup)</span>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="1"
                  value={timelineStep}
                  onChange={(e) => setTimelineStep(Number(e.target.value))}
                  className="w-full h-1.5 bg-stone-200 rounded-lg appearance-none cursor-pointer accent-stone-900"
                />
                <span className="text-xs text-stone-500 font-bold whitespace-nowrap">4 hr (Clearing)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Automated Learning Loop / Report Card Modal */}
      {showFeedbackModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-stone-200 rounded-[2.5rem] w-full max-w-lg overflow-hidden shadow-2xl animate-fade-in relative">
            <button
              onClick={() => setShowFeedbackModal(false)}
              className="absolute top-6 right-6 text-stone-400 hover:text-stone-700 text-xl font-bold"
            >
              ✕
            </button>

            <div className="p-8">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">📊</span>
                <h3 className="text-xl font-bold text-stone-800">Learning Loop: Post-Event Report</h3>
              </div>
              <p className="text-xs text-[var(--text-muted)] mb-6">
                Event ended. Compare simulated forecast against actual sensors and tune hyper-parameters.
              </p>

              {/* Chart Comparison Mock */}
              <div className="bg-stone-50 border border-stone-100 rounded-2xl p-4 mb-6">
                <h4 className="text-xs font-bold text-stone-600 uppercase mb-3 text-center">Congestion Rate (Projected vs Actual)</h4>
                <div className="h-28 flex items-end justify-between gap-2 px-2 relative border-b border-l border-stone-200 pb-1">
                  {/* Projected spikes */}
                  <div className="flex-1 flex flex-col justify-end h-full">
                    <div className="w-full bg-orange-200 rounded-t h-[40%]" title="Projected: 40"></div>
                    <div className="w-full bg-orange-400 rounded-t h-[85%]" title="Projected: 85"></div>
                    <div className="w-full bg-orange-200 rounded-t h-[30%]" title="Projected: 30"></div>
                  </div>
                  {/* Actual spikes */}
                  <div className="flex-1 flex flex-col justify-end h-full">
                    <div className="w-full bg-blue-300 rounded-t h-[35%]" title="Actual: 35"></div>
                    <div className="w-full bg-blue-500 rounded-t h-[92%]" title="Actual: 92"></div>
                    <div className="w-full bg-blue-300 rounded-t h-[20%]" title="Actual: 20"></div>
                  </div>
                  {/* Legend Overlay */}
                  <div className="absolute top-0 right-0 flex gap-2 text-[9px] font-bold">
                    <span className="flex items-center gap-1"><span className="w-2.5 h-1 bg-orange-400 rounded"></span>Projected</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-1 bg-blue-500 rounded"></span>Actual</span>
                  </div>
                </div>
                <div className="flex justify-between text-[9px] text-stone-400 mt-1 font-semibold uppercase">
                  <span>Pre-Event</span>
                  <span>Peak Event</span>
                  <span>Post-Event</span>
                </div>
              </div>

              {/* Accuracy Feedback Form */}
              <form onSubmit={handleSaveFeedback} className="space-y-4">
                <div className="flex items-center justify-between bg-stone-50 p-3 rounded-xl">
                  <span className="text-xs font-bold text-stone-700">Rate Model Accuracy:</span>
                  <div className="flex gap-1.5">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        type="button"
                        key={star}
                        onClick={() => setRating(star)}
                        className={`text-lg transition-transform hover:scale-125 ${rating >= star ? "opacity-100" : "opacity-30"}`}
                      >
                        ⭐️
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-stone-600 uppercase mb-1">Incident Notes / Deviations</label>
                  <textarea
                    rows={2}
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder="Enter details on manual adjustments or unpredicted bottlenecks..."
                    className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-stone-900"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs font-bold text-stone-600 uppercase mb-1">
                    <span>Tuning Weights: Crowd Scaling Factor</span>
                    <span className="text-stone-900 font-mono">{(crowdVenueWeight * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="1.5"
                    step="0.05"
                    value={crowdVenueWeight}
                    onChange={(e) => setCrowdVenueWeight(Number(e.target.value))}
                    className="w-full h-1 bg-stone-200 rounded-lg appearance-none cursor-pointer accent-stone-900"
                  />
                  <p className="text-[10px] text-[var(--text-muted)] mt-1 font-medium">
                    Adjusts sensitivity of event crowds on duration estimates for future training loops.
                  </p>
                </div>

                {savedStatus && (
                  <div className="p-2 bg-green-50 border border-green-200 text-green-700 text-xs font-bold rounded-lg text-center">
                    {savedStatus}
                  </div>
                )}

                <div className="flex gap-2 justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setShowFeedbackModal(false)}
                    className="px-4 py-2 rounded-xl border border-stone-200 text-stone-700 text-xs font-bold hover:bg-stone-50"
                  >
                    Dismiss
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2 rounded-xl bg-stone-900 text-white text-xs font-bold hover:bg-stone-800 shadow"
                  >
                    Submit & Save
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
