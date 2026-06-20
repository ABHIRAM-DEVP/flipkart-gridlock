import React from 'react';
import { SoftCard } from './SoftCard';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  Cell, 
} from 'recharts';
import { BarChart2 } from 'lucide-react';

// --- Type Definitions ---
// Define the shape of your specific chart data
interface ChartDataPoint {
  fullName: string;
  name: string;
  weight: number;
  original: number;
}

const CustomTooltip = ({ active, payload }: any) => {
  // 1. Check if the tooltip is active and payload exists
  if (active && payload && payload.length > 0) {
    
    // 2. Cast the payload to your specific interface to satisfy TypeScript
    const d = payload[0].payload as ChartDataPoint;

    return (
      <div style={{ 
        background: 'rgba(255,255,255,0.95)', 
        backdropFilter: 'blur(10px)', 
        borderRadius: '1rem', 
        border: '1px solid rgba(0,0,0,0.06)', 
        padding: '0.6rem 0.9rem', 
        boxShadow: '0 4px 20px rgba(0,0,0,0.08)' 
      }}>
        <p style={{ margin: 0, fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '2px' }}>
          {d.fullName}
        </p>
        <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Importance: <b style={{ color: 'var(--text-main)' }}>{Math.abs(d.original).toFixed(5)}</b>
        </p>
      </div>
    );
  }
  return null;
};

const EmptyChart = () => (
  <SoftCard className="h-full">
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
      <div style={{ width: '32px', height: '32px', borderRadius: '10px', background: 'rgba(255,183,178,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <BarChart2 size={16} color="var(--accent-coral)" />
      </div>
      <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Top Features Impacting Duration</h3>
    </div>
    <div style={{ height: '220px', display: 'flex', flexDirection: 'column', justifyContent: 'space-around', padding: '0.5rem 0' }}>
      {[85, 70, 62, 55, 48, 38, 30].map((w, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: '90px', height: '11px', borderRadius: '6px', background: 'linear-gradient(90deg, #f3f2ef 25%, #eae9e5 50%, #f3f2ef 75%)', backgroundSize: '200% 100%', animation: `shimmer 1.5s ${i * 0.1}s infinite` }} />
          <div style={{ height: '14px', borderRadius: '0 6px 6px 0', background: 'linear-gradient(90deg, #f3f2ef 25%, #eae9e5 50%, #f3f2ef 75%)', backgroundSize: '200% 100%', animation: `shimmer 1.5s ${i * 0.1}s infinite`, width: `${w}%`, maxWidth: 'calc(100% - 110px)' }} />
        </div>
      ))}
    </div>
    <p style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
      Feature importance will appear once the AI service connects.
    </p>
    <style>{`@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }`}</style>
  </SoftCard>
);

const CORAL_PALETTE = ['#FFB7B2', '#FFA89F', '#FF998C', '#FF8A79', '#F07B6A', '#E06C5B'];

export const FeatureWeightsChart = ({ data }: { data: any[] }) => {
  if (!data || !Array.isArray(data) || data.length === 0) {
    return <EmptyChart />;
  }

  const chartData: ChartDataPoint[] = data
    .map((item) => ({
      fullName: item.feature,
      name: item.feature.replace(/^(feature_|feat_)/, '').replace(/_/g, ' ').slice(0, 18),
      weight: Math.abs(item.importance ?? item.gain ?? item.coefficient ?? item.weight ?? 0),
      original: item.importance ?? item.gain ?? item.coefficient ?? item.weight ?? 0,
    }))
    .filter(d => d.weight > 0)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 10);

  return (
    <SoftCard className="h-full">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <div style={{ width: '32px', height: '32px', borderRadius: '10px', background: 'rgba(255,183,178,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <BarChart2 size={16} color="var(--accent-coral)" />
        </div>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Top Features Impacting Duration</h3>
        <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.04)', borderRadius: '6px', padding: '2px 8px' }}>
          top {chartData.length}
        </span>
      </div>
      <div style={{ height: '240px', width: '100%' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
            <XAxis type="number" hide domain={[0, 'dataMax']} />
            <YAxis
              dataKey="name"
              type="category"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'var(--font-primary)' }}
              width={110}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)', rx: 4 }} />
            <Bar dataKey="weight" radius={[0, 6, 6, 0]} maxBarSize={14}>
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={CORAL_PALETTE[index % CORAL_PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </SoftCard>
  );
};
