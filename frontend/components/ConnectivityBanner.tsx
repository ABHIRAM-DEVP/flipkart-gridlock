"use client";

import React, { useEffect, useState, useCallback } from 'react';
import { checkHealth } from '@/lib/api';

export const ConnectivityBanner = () => {
  const [status, setStatus] = useState<'checking' | 'ok' | 'unreachable'>('checking');
  const [retryCount, setRetryCount] = useState(0);

  const check = useCallback(async () => {
    try {
      const res = await checkHealth();
      setStatus(res.astramService === 'unreachable' ? 'unreachable' : 'ok');
    } catch {
      setStatus('unreachable');
    }
  }, []);

  useEffect(() => {
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [check, retryCount]);

  if (status === 'checking' || status === 'ok') return null;

  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[100] w-[calc(100%-2rem)] max-w-md">
      <div style={{
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(20px)',
        borderRadius: '1.5rem',
        border: '1px solid rgba(239,68,68,0.2)',
        boxShadow: '0 8px 32px -4px rgba(239,68,68,0.15), 0 2px 8px rgba(0,0,0,0.06)',
        padding: '1rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.875rem',
      }}>
        {/* Pulsing dot */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <div style={{
            width: '10px', height: '10px', borderRadius: '50%',
            background: '#ef4444',
            animation: 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
          }} />
          <div style={{
            position: 'absolute', inset: '-4px',
            borderRadius: '50%',
            background: 'rgba(239,68,68,0.25)',
            animation: 'ping 1.5s cubic-bezier(0,0,0.2,1) infinite',
          }} />
        </div>

        {/* Icon + text */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: '#292524' }}>
            AI Service Unreachable
          </p>
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#78716c', marginTop: '2px' }}>
            Dashboard will update when the model service comes online.
          </p>
        </div>

        {/* Retry button */}
        <button
          onClick={() => setRetryCount(c => c + 1)}
          style={{
            flexShrink: 0,
            fontSize: '0.75rem',
            fontWeight: 600,
            color: '#ef4444',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: '0.75rem',
            padding: '0.35rem 0.75rem',
            cursor: 'pointer',
            transition: 'background 0.2s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.15)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}
        >
          Retry
        </button>
      </div>
      <style>{`
        @keyframes ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
};
