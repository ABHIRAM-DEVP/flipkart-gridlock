import React from 'react';
import { SoftCard } from './SoftCard';
import { Activity, Clock, TrendingUp, AlertTriangle } from 'lucide-react';

const StatRow = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.65rem 0', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{label}</span>
    <span style={{ fontSize: '0.875rem', fontWeight: 600, color: color || 'var(--text-main)' }}>{value}</span>
  </div>
);

const EmptyMetrics = () => (
  <SoftCard className="h-full flex flex-col">
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
      <div style={{
        width: '32px', height: '32px', borderRadius: '10px',
        background: 'rgba(255,183,178,0.15)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Activity size={16} color="var(--accent-coral)" />
      </div>
      <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Model Performance</h3>
    </div>

    {/* Skeleton rows */}
    {['Duration R²', 'MAE (Duration)', 'Severity Accuracy'].map((label) => (
      <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.65rem 0', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{label}</span>
        <div style={{ height: '14px', width: '60px', borderRadius: '7px', background: 'linear-gradient(90deg, #f3f2ef 25%, #eae9e5 50%, #f3f2ef 75%)', backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite' }} />
      </div>
    ))}

    <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <AlertTriangle size={13} color="var(--text-muted)" />
      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Awaiting AI service connection…</span>
    </div>
    <style>{`@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }`}</style>
  </SoftCard>
);

export const MetricsSummaryCard = ({ metrics }: { metrics: any }) => {
  if (!metrics) return <EmptyMetrics />;

  const r2 = metrics.duration_r2 ?? metrics.r2;
  const mae = metrics.duration_mae_min ?? metrics.duration_mae ?? metrics.mae;
  const acc = metrics.severity_accuracy;
  const f1 = metrics.severity_f1_macro ?? metrics.severity_f1;

  const r2Color = r2 != null ? (r2 > 0.6 ? '#22c55e' : r2 > 0.3 ? '#f59e0b' : '#ef4444') : undefined;

  return (
    <SoftCard className="h-full flex flex-col">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '10px',
          background: 'rgba(255,183,178,0.15)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Activity size={16} color="var(--accent-coral)" />
        </div>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Model Performance</h3>
      </div>

      <div style={{ flex: 1 }}>
        <StatRow label="R² Score (Duration)" value={r2 != null ? r2.toFixed(4) : 'N/A'} color={r2Color} />
        <StatRow label="MAE (Duration)" value={mae != null ? `${mae.toFixed(1)} min` : 'N/A'} />
        <StatRow label="Severity Accuracy" value={acc != null ? `${(acc * 100).toFixed(1)}%` : 'N/A'} />
        {f1 != null && <StatRow label="F1 Macro" value={f1.toFixed(3)} />}
      </div>

      <div style={{ marginTop: '1rem', paddingTop: '0.875rem', borderTop: '1px solid rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Clock size={13} color="var(--text-muted)" />
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {metrics.training_time ? `Last trained: ${metrics.training_time}` : 'Live model data'}
        </span>
        <TrendingUp size={13} color="#22c55e" style={{ marginLeft: 'auto' }} />
      </div>
    </SoftCard>
  );
};
