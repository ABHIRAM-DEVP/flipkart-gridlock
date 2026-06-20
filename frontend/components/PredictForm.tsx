"use client";

import React, { useState } from "react";
import { SoftCard } from "@/components/SoftCard";
import { predict } from "@/lib/api";

type PredictFormState = {
  start_datetime: string;
  event_type: string;
  event_cause: string;
  corridor: string;
  zone: string;
  junction: string;
  latitude: string;
  longitude: string;
  priority: string;
  requires_road_closure: boolean;
  address: string;
};

const SAMPLE: PredictFormState = {
  start_datetime: "2026-06-20T08:30",
  event_type: "unplanned",
  event_cause: "vehicle_breakdown",
  corridor: "Tumkur Road",
  zone: "North",
  junction: "Yeshwantpur",
  latitude: "13.0140",
  longitude: "77.5608",
  priority: "high",
  requires_road_closure: false,
  address: "Near Yeshwantpur Metro, Pin-560022",
};

export const PredictForm = ({ onNewPrediction }: { onNewPrediction: () => void }) => {
  const [formData, setFormData] = useState<PredictFormState>(SAMPLE);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const payload = {
        ...formData,
        latitude: parseFloat(formData.latitude),
        longitude: parseFloat(formData.longitude),
        requires_road_closure: formData.requires_road_closure,
      };
      const res = await predict(payload);
      const parsed = res.responsePayload ? JSON.parse(res.responsePayload) : res;
      setResult(parsed);
      onNewPrediction();
    } catch (err: any) {
      setError(err.error || err.details || "Failed to submit prediction request");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target;
    const nextValue = type === "checkbox" ? (e.target as HTMLInputElement).checked : value;
    setFormData((current) => ({ ...current, [name]: nextValue as never }));
  };

  const fields = [
    ["start_datetime", "Start DateTime", "datetime-local"],
    ["event_type", "Event Type", "text"],
    ["event_cause", "Event Cause", "text"],
    ["corridor", "Corridor", "text"],
    ["zone", "Zone", "text"],
    ["junction", "Junction", "text"],
    ["latitude", "Latitude", "number"],
    ["longitude", "Longitude", "number"],
    ["priority", "Priority", "text"],
    ["address", "Address", "text"],
  ] as const;

  return (
    <SoftCard>
      <div className="flex flex-col gap-2 mb-6">
        <h2 className="text-2xl font-medium">Score Single Incident</h2>
        <p className="text-sm text-[var(--text-muted)]">
          Use the same fields the model was trained on so the prediction is meaningful.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fields.map(([name, label, type]) => (
            <div key={name}>
              <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">{label}</label>
              <input
                required={name !== "address"}
                type={type}
                name={name}
                value={String(formData[name])}
                onChange={handleChange}
                className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-[var(--accent-coral)]"
              />
            </div>
          ))}
          <div className="flex items-center gap-3 pt-6">
            <input
              id="requires_road_closure"
              type="checkbox"
              name="requires_road_closure"
              checked={formData.requires_road_closure}
              onChange={handleChange}
              className="h-4 w-4 rounded border-stone-300 text-[var(--accent-coral)] focus:ring-[var(--accent-coral)]"
            />
            <label htmlFor="requires_road_closure" className="text-sm text-[var(--text-muted)]">
              Requires road closure
            </label>
          </div>
        </div>

        {error && <div className="text-red-500 text-sm mt-2">{error}</div>}

        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="button"
            onClick={() => setFormData(SAMPLE)}
            className="px-4 py-2 rounded-xl border border-stone-200 text-sm text-[var(--text-main)] hover:bg-stone-50 transition-colors"
          >
            Load sample
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex-1 min-w-[220px] px-6 py-3 rounded-xl bg-[var(--text-main)] text-white font-medium hover:bg-stone-800 transition-colors disabled:opacity-50"
          >
            {loading ? "Scoring..." : "Predict Incident Impact"}
          </button>
        </div>
      </form>

      {result && (
        <div className="mt-8 p-4 bg-[var(--accent-sage)] rounded-xl">
          <h3 className="font-medium text-stone-800 mb-2">Prediction Result</h3>
          <pre className="text-sm overflow-x-auto text-stone-700 bg-white/50 p-4 rounded-lg">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </SoftCard>
  );
};
