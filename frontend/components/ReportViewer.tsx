"use client";

import React, { useEffect, useState } from 'react';
import { SoftCard } from '@/components/SoftCard';
import { getReportText, getGraphFiles, getGraphImageUrl } from '@/lib/api';

export const ReportViewer = () => {
  const [report, setReport] = useState<string | null>(null);
  const [graphs, setGraphs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [reportText, graphList] = await Promise.all([
          getReportText(),
          getGraphFiles()
        ]);
        setReport(reportText);
        const manifest = graphList as any;
        setGraphs(Array.isArray(manifest) ? manifest : manifest?.graphs || []);
      } catch (err) {
        console.error("Failed to load reports", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return <div className="text-[var(--text-muted)] animate-pulse py-8 text-center">Loading report and graphs...</div>;
  }

  return (
    <div className="space-y-8">
      <SoftCard>
        <h2 className="text-2xl font-medium mb-6">Execution Report</h2>
        {report ? (
          <pre className="text-sm bg-stone-50 p-6 rounded-xl border border-stone-100 overflow-x-auto whitespace-pre-wrap font-mono text-stone-700">
            {report}
          </pre>
        ) : (
          <div className="text-[var(--text-muted)]">No report available.</div>
        )}
      </SoftCard>

      <SoftCard>
        <h2 className="text-2xl font-medium mb-6">Generated Graphs</h2>
        {graphs.length === 0 ? (
          <div className="text-[var(--text-muted)]">No graph files available.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {graphs.map((graph: any) => {
              const filename = typeof graph === "string" ? graph : graph.name || graph.path || "graph.png";
              return (
              <div key={filename} className="border border-stone-100 rounded-xl overflow-hidden hover:shadow-[var(--shadow-soft)] transition-shadow">
                <div className="p-3 bg-stone-50 border-b border-stone-100 font-mono text-xs text-[var(--text-muted)] truncate">
                  {filename}
                </div>
                <img 
                  src={getGraphImageUrl(filename)} 
                  alt={filename} 
                  className="w-full h-auto"
                />
              </div>
            )})}
          </div>
        )}
      </SoftCard>
    </div>
  );
};
