"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { SoftCard } from '@/components/SoftCard';

export const LoginScreen = ({ nextPath }: { nextPath: string }) => {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.details || 'Login failed');
      }

      router.replace(nextPath);
      router.refresh();
    } catch (err: any) {
      setError(err?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SoftCard className="self-center border-stone-200">
      <div className="space-y-6">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-[var(--text-muted)]">Workspace login</p>
          <h2 className="mt-2 text-3xl font-light tracking-tight text-[var(--text-main)]">Welcome back</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">
            Use the configured credentials to continue.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--text-main)]">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-[var(--text-main)] outline-none transition focus:border-[var(--accent-coral)] focus:ring-2 focus:ring-[rgba(255,183,178,0.35)]"
              placeholder="astram-admin"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--text-main)]">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-[var(--text-main)] outline-none transition focus:border-[var(--accent-coral)] focus:ring-2 focus:ring-[rgba(255,183,178,0.35)]"
              placeholder="astram-demo"
            />
          </div>

          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-2xl bg-[var(--text-main)] px-4 py-3 font-medium text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>




      </div>
    </SoftCard>
  );
};

