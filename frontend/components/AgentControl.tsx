"use client";

import React, { useEffect, useState } from "react";
import { runAgent, subscribeSSE } from "@/lib/api";

export const AgentControl = () => {
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    const unsub = subscribeSSE((msg) => {
      setLogs((l) => [msg, ...l].slice(0, 50));
    });
    return () => unsub();
  }, []);

  const start = async () => {
    setRunning(true);
    try {
      await runAgent({});
    } catch (err: any) {
      setLogs((l) => [{ type: "error", payload: err }, ...l]);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <button
          onClick={start}
          disabled={running}
          className="px-4 py-2 rounded-xl bg-[var(--accent-coral)] text-white"
        >
          {running ? "Running agent..." : "Run Agentic Workflow"}
        </button>
        <div className="text-sm text-[var(--text-muted)]">Agent guides Predict {"→"} Plan {"→"} Impact</div>
      </div>

      <div className="max-h-56 overflow-auto p-3 bg-white/60 rounded-lg border">
        {logs.length === 0 && <div className="text-[var(--text-muted)]">No events yet.</div>}
        {logs.map((item, i) => (
          <div key={i} className="text-xs py-1 border-b last:border-b-0">
            <strong className="mr-2">{item.type}</strong>
            <span className="text-[var(--text-muted)]">{JSON.stringify(item.payload || item)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
