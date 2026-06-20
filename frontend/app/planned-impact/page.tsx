"use client";

import React, { useEffect, useState } from 'react';
import { PlannedImpactForm } from '@/components/PlannedImpactForm';
import { SoftCard } from '@/components/SoftCard';
import { getPlannedImpactHistory } from '@/lib/api';

export default function PlannedImpactPage() {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      const res = await getPlannedImpactHistory();
      setHistory(res.content || []);
    } catch (err) {
      console.error("Failed to fetch impact history", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <div className="space-y-8 animate-in fade-in duration-700 max-w-4xl mx-auto">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-light tracking-tight mb-2">
          Planned <span className="font-['Reenie_Beanie'] text-5xl text-[var(--accent-coral)]">Impact</span>
        </h1>
        <p className="text-[var(--text-muted)]">Forecast spillover impact for major scheduled events.</p>
      </header>

      <PlannedImpactForm onNewImpact={fetchHistory} />

      <SoftCard>
        <h2 className="text-xl font-medium mb-4">Forecast History</h2>
        {loading ? (
          <div className="text-[var(--text-muted)] py-4 animate-pulse">Loading history...</div>
        ) : history.length === 0 ? (
          <div className="text-[var(--text-muted)] py-4">No impact forecast history.</div>
        ) : (
          <div className="space-y-4">
            {history.map(h => (
              <div key={h.id} className="p-4 border border-stone-100 rounded-xl hover:bg-stone-50 transition-colors">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-[var(--text-muted)]">{new Date(h.requestedAt).toLocaleString()}</span>
                </div>
                <div className="text-xs font-mono text-stone-500 overflow-x-auto truncate">
                  {h.requestPayload}
                </div>
              </div>
            ))}
          </div>
        )}
      </SoftCard>
    </div>
  );
}
