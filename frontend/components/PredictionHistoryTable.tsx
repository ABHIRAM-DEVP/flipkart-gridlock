import React from 'react';

export const PredictionHistoryTable = ({ history }: { history: any[] }) => {
  if (!history || history.length === 0) {
    return <div className="text-[var(--text-muted)] py-4">No prediction history yet.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-stone-100 text-[var(--text-muted)] text-sm">
            <th className="pb-3 font-medium px-4">Time</th>
            <th className="pb-3 font-medium px-4">Est. Duration</th>
            <th className="pb-3 font-medium px-4">Severity</th>
            <th className="pb-3 font-medium px-4">Payload Snippet</th>
          </tr>
        </thead>
        <tbody className="text-sm">
          {history.map((h) => {
            const date = new Date(h.requestedAt).toLocaleString();
            let reqSnippet = h.requestPayload;
            if (reqSnippet && reqSnippet.length > 50) {
              reqSnippet = reqSnippet.substring(0, 50) + '...';
            }
            return (
              <tr key={h.id} className="border-b border-stone-50 hover:bg-stone-50/50 transition-colors">
                <td className="py-4 px-4 text-[var(--text-muted)]">{date}</td>
                <td className="py-4 px-4 font-medium">
                  {h.durationEstimate != null
                    ? h.durationEstimate.toFixed(2)
                    : h.predictedDurationMin != null
                      ? Number(h.predictedDurationMin).toFixed(2)
                      : '-'}
                </td>
                <td className="py-4 px-4">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${String(h.severityLabel || h.predictedSeverity || '').toLowerCase() === 'high' ? 'bg-red-100 text-red-800' : 'bg-stone-100 text-stone-800'}`}>
                    {h.severityLabel || h.predictedSeverity || '-'}
                  </span>
                </td>
                <td className="py-4 px-4 text-xs font-mono text-stone-500 break-all">{reqSnippet}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
