import React from 'react';
import { SoftCard } from './SoftCard';

export const PlanResultsTable = ({ result }: { result: any }) => {
  if (!result || !result.scored_events) return null;

  return (
    <div className="space-y-6 mt-8">
      <SoftCard className="bg-[var(--accent-sage)] border-none">
        <h3 className="text-lg font-semibold mb-2">Allocation Strategy</h3>
        <pre className="text-sm overflow-x-auto text-stone-700 bg-white/50 p-4 rounded-lg">
          {JSON.stringify(result.allocation, null, 2)}
        </pre>
      </SoftCard>

      <div className="overflow-x-auto">
        <h3 className="text-lg font-medium mb-4 px-2">Scored Events</h3>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-stone-200 text-[var(--text-muted)] text-sm">
              <th className="pb-3 font-medium px-4">Event Type</th>
              <th className="pb-3 font-medium px-4">Priority</th>
              <th className="pb-3 font-medium px-4">Predicted Duration</th>
              <th className="pb-3 font-medium px-4">Predicted Severity</th>
            </tr>
          </thead>
          <tbody className="text-sm bg-white rounded-xl">
            {result.scored_events.map((e: any, i: number) => {
              const event = e.event || {};
              const pred = e.prediction || {};
              return (
                <tr key={i} className="border-b border-stone-50 hover:bg-stone-50 transition-colors">
                  <td className="py-3 px-4 font-medium">{event.event_type}</td>
                  <td className="py-3 px-4">{event.priority}</td>
                  <td className="py-3 px-4 text-[var(--accent-coral)] font-semibold">{(pred.predicted_duration_min ?? pred.duration_estimate)?.toFixed?.(2) || 'N/A'}</td>
                  <td className="py-3 px-4">{pred.predicted_severity || pred.severity_label || 'N/A'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
