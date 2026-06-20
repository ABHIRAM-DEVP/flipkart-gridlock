"use client";

import React, { useEffect, useState } from 'react';
import { PlanForm } from '@/components/PlanForm';
import { PlanResultsTable } from '@/components/PlanResultsTable';
import { SoftCard } from '@/components/SoftCard';
import { getPlanHistory } from '@/lib/api';

export default function PlanPage() {
  const [history, setHistory] = useState<any[]>([]);
  const [currentResult, setCurrentResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      const res = await getPlanHistory();
      setHistory(res.content || []);
    } catch (err) {
      console.error("Failed to fetch plan history", err);
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
          Batch <span className="font-['Reenie_Beanie'] text-5xl text-[var(--accent-coral)]">Planning</span>
        </h1>
        <p className="text-[var(--text-muted)]">Score multiple events and allocate resources against a budget.</p>
      </header>

      <PlanForm onNewPlan={fetchHistory} onResult={setCurrentResult} />

      {currentResult && (
        <SoftCard>
          <h2 className="text-xl font-medium mb-4">Latest Plan Results</h2>
          <PlanResultsTable result={currentResult} />
        </SoftCard>
      )}

      <SoftCard>
        <h2 className="text-xl font-medium mb-4">Plan History</h2>
        {loading ? (
          <div className="text-[var(--text-muted)] py-4 animate-pulse">Loading history...</div>
        ) : history.length === 0 ? (
          <div className="text-[var(--text-muted)] py-4">No planning history.</div>
        ) : (
          <div className="space-y-4">
            {history.map(h => (
              <div key={h.id} className="p-4 border border-stone-100 rounded-xl hover:bg-stone-50 transition-colors">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-[var(--text-muted)]">{new Date(h.requestedAt).toLocaleString()}</span>
                  <span className="text-sm font-medium">Budget: {h.budget} | Events: {h.eventCount}</span>
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
