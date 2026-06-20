"use client";

import React, { useEffect, useState } from "react";
import { getDbscanHotspots, getHotspots, getMetrics, getPredictionsHistory, getWeights } from "@/lib/api";
import { SoftCard } from "@/components/SoftCard";
import { MetricsSummaryCard } from "@/components/MetricsSummaryCard";
import { FeatureWeightsChart } from "@/components/FeatureWeightsChart";
import { HotspotsMap } from "@/components/HotspotsMap";
import { PredictionHistoryTable } from "@/components/PredictionHistoryTable";

const problemCards = [
  {
    title: "Event-Driven Congestion",
    text: "Planned & unplanned incidents collapse throughput in localized corridors and spill into adjacent road networks.",
  },
  {
    title: "Operational Challenge",
    text: "Political rallies, festivals, sports events, construction activities, and sudden gatherings create localized traffic breakdowns.",
  },
  {
    title: "Why It’s Hard Today",
    text: "Impact is not quantified in advance, resource deployment is experience-driven, and post-event learning is usually missing.",
  },
];

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>(null);
  const [weights, setWeights] = useState<any>(null);
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [dbscanHotspots, setDbscanHotspots] = useState<any[]>([]);
  const [predictions, setPredictions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        const [mRes, wRes, hRes, dRes, pRes] = await Promise.all([
          getMetrics(),
          getWeights("duration", 10),
          getHotspots(),
          getDbscanHotspots(),
          getPredictionsHistory(),
        ]);
        if (!mounted) return;
        setMetrics(mRes);
        setWeights(wRes);
        setHotspots(hRes);
        setDbscanHotspots(dRes);
        setPredictions(pRes?.content || []);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (err) {
        console.error("Dashboard fetch error:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchData();
    const timer = setInterval(fetchData, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  if (loading) {
    return <div className="flex justify-center items-center h-64 text-[var(--text-muted)] animate-pulse">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-700">
      <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <SoftCard className="relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,183,178,0.35),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(232,239,232,0.6),transparent_32%)]" />
          <div className="relative space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-[var(--text-muted)]">
              Live traffic intelligence
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
            </div>
            <div>
              <h1 className="text-4xl md:text-5xl font-light tracking-tight leading-tight">
                Forecast and manage congestion before it spreads across the corridor.
              </h1>
              <p className="mt-4 max-w-2xl text-[var(--text-muted)] text-base leading-7">
                Historical event data plus real-time scoring powers duration prediction, manpower planning, barricading, diversion guidance, and closed-loop learning.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {problemCards.map((card) => (
                <div key={card.title} className="rounded-2xl border border-white/60 bg-white/65 p-4 shadow-[0_6px_22px_rgba(0,0,0,0.04)] backdrop-blur-sm">
                  <h3 className="text-sm font-semibold text-[var(--text-main)]">{card.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{card.text}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-3 text-xs text-[var(--text-muted)]">
              <span className="rounded-full border border-stone-200 bg-white/70 px-3 py-1">Updated: {lastUpdated || "just now"}</span>
              <span className="rounded-full border border-stone-200 bg-white/70 px-3 py-1">Live refresh every 15s</span>
              <span className="rounded-full border border-stone-200 bg-white/70 px-3 py-1">Fallback mode available</span>
            </div>
          </div>
        </SoftCard>

        <MetricsSummaryCard metrics={metrics} />
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <FeatureWeightsChart data={weights} />
        <SoftCard>
          <div className="flex items-center justify-between mb-5">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">Recent predictions</p>
              <h2 className="text-2xl font-medium">Real-time feed</h2>
            </div>
            <span className="rounded-full bg-[var(--accent-lavender)] px-3 py-1 text-xs font-medium text-[var(--text-main)]">
              {predictions.length} latest records
            </span>
          </div>
          <PredictionHistoryTable history={predictions.slice(0, 5)} />
        </SoftCard>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <SoftCard>
          <div className="mb-5">
            <p className="text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">Operational heat map</p>
            <h2 className="text-2xl font-medium">DBSCAN congestion clusters</h2>
          </div>
          <HotspotsMap hotspots={dbscanHotspots} />
        </SoftCard>

        <SoftCard>
          <div className="mb-5">
            <p className="text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">Recurring hotspots</p>
            <h2 className="text-2xl font-medium">Historical corridor impact</h2>
          </div>
          <div className="space-y-3">
            {hotspots.slice(0, 8).map((item, index) => (
              <div key={index} className="rounded-2xl border border-stone-100 bg-stone-50/60 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="font-medium text-[var(--text-main)]">{item.name}</div>
                    <div className="text-sm text-[var(--text-muted)]">
                      {item.count} events · avg {Number(item.avg_duration_min ?? item.avg_duration ?? 0).toFixed(1)} min
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-[var(--text-main)]">{Number(item.hotspot_score ?? 0).toFixed(1)}</div>
                    <div className="text-xs text-[var(--text-muted)]">risk score</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </SoftCard>
      </section>
    </div>
  );
}
