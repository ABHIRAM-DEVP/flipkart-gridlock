"use client";

import React, { useEffect, useState } from 'react';
import { PredictForm } from '@/components/PredictForm';
import { PredictionHistoryTable } from '@/components/PredictionHistoryTable';
import { SoftCard } from '@/components/SoftCard';
import { getPredictionsHistory } from '@/lib/api';

export default function PredictPage() {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      const res = await getPredictionsHistory();
      setHistory(res.content || []);
    } catch (err) {
      console.error("Failed to fetch prediction history", err);
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
          Event <span className="font-['Reenie_Beanie'] text-5xl text-[var(--accent-coral)]">Prediction</span>
        </h1>
        <p className="text-[var(--text-muted)]">Score individual incidents and forecast impact.</p>
      </header>

      <PredictForm onNewPrediction={fetchHistory} />

      <SoftCard>
        <h2 className="text-xl font-medium mb-4">Prediction History</h2>
        {loading ? (
          <div className="text-[var(--text-muted)] py-4 animate-pulse">Loading history...</div>
        ) : (
          <PredictionHistoryTable history={history} />
        )}
      </SoftCard>
    </div>
  );
}
