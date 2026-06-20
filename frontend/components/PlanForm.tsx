"use client";

import React, { useState } from 'react';
import { SoftCard } from '@/components/SoftCard';
import { plan } from '@/lib/api';

export const PlanForm = ({ onNewPlan, onResult }: { onNewPlan: () => void, onResult: (res: any) => void }) => {
  const [eventsJson, setEventsJson] = useState('[\n  {\n    "start_datetime": "2026-06-20T18:00",\n    "event_type": "planned",\n    "event_cause": "festival",\n    "corridor": "Old Madras Road",\n    "zone": "East",\n    "junction": "KR Puram",\n    "latitude": 13.0069,\n    "longitude": 77.6950,\n    "priority": "high",\n    "requires_road_closure": true\n  }\n]');
  const [budget, setBudget] = useState('50');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let eventsArray = [];
      try {
        eventsArray = JSON.parse(eventsJson);
      } catch (e) {
        throw new Error("Invalid JSON in events array");
      }

      if (!Array.isArray(eventsArray)) {
        throw new Error("Events must be a JSON array");
      }

      const payload = {
        events: eventsArray,
        budget: parseInt(budget, 10) || 50
      };

      const res = await plan(payload);
      onResult(res.responsePayload ? JSON.parse(res.responsePayload) : res);
      onNewPlan();
    } catch (err: any) {
      setError(err.message || err.error || 'Failed to submit plan request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SoftCard>
      <h2 className="text-2xl font-medium mb-6">Batch Planning</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">Events Array (JSON)</label>
          <textarea 
            required 
            rows={10} 
            value={eventsJson} 
            onChange={(e) => setEventsJson(e.target.value)} 
            className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-[var(--accent-coral)] font-mono text-sm" 
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">Resource Budget</label>
          <input 
            required 
            type="number" 
            min="1" 
            value={budget} 
            onChange={(e) => setBudget(e.target.value)} 
            className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-[var(--accent-coral)]" 
          />
        </div>

        {error && <div className="text-red-500 text-sm mt-2">{error}</div>}
        
        <button 
          type="submit" 
          disabled={loading}
          className="mt-6 w-full px-6 py-3 rounded-xl bg-[var(--text-main)] text-white font-medium hover:bg-stone-800 transition-colors disabled:opacity-50"
        >
          {loading ? 'Processing...' : 'Run Plan'}
        </button>
      </form>
    </SoftCard>
  );
};
