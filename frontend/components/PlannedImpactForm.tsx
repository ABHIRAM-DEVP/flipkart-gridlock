"use client";

import React, { useState } from "react";
import { SoftCard } from "@/components/SoftCard";
import { plannedImpact } from "@/lib/api";

type PlannedImpactState = {
  start_datetime: string;
  event_type: string;
  event_cause: string;
  corridor: string;
  zone: string;
  junction: string;
  latitude: string;
  longitude: string;
  priority: string;
  address: string;
};

const SAMPLE: PlannedImpactState = {
  start_datetime: "2026-06-20T18:00",
  event_type: "planned",
  event_cause: "festival",
  corridor: "Old Madras Road",
  zone: "East",
  junction: "KR Puram",
  latitude: "13.0069",
  longitude: "77.6950",
  priority: "high",
  address: "KR Puram, Bangalore, Pin-560016",
};

export const PlannedImpactForm = ({ onNewImpact }: { onNewImpact: () => void }) => {
  const [formData, setFormData] = useState<PlannedImpactState>(SAMPLE);
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
      };
      const res = await plannedImpact(payload);
      setResult(res.responsePayload ? JSON.parse(res.responsePayload) : res);
      onNewImpact();
    } catch (err: any) {
      setError(err.error || err.details || "Failed to submit planned impact forecast");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((current) => ({ ...current, [name]: value }));
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
        <h2 className="text-2xl font-medium">Forecast Planned Event Impact</h2>
        <p className="text-sm text-[var(--text-muted)]">
          Simulate scheduled events and estimate spillover before deployment.
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
            {loading ? "Forecasting..." : "Forecast Impact"}
          </button>
        </div>
      </form>

      {result && (
        <div className="mt-8 p-4 bg-[var(--accent-sage)] rounded-xl">
          <h3 className="font-medium text-stone-800 mb-2">Spillover Stats</h3>
          <pre className="text-sm overflow-x-auto text-stone-700 bg-white/50 p-4 rounded-lg">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </SoftCard>
  );
};
