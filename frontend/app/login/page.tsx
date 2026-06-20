import { LoginScreen } from '@/components/LoginScreen';

export default function LoginPage({
  searchParams,
}: {
  searchParams: { next?: string };
}) {
  const nextPath = typeof searchParams?.next === 'string' && searchParams.next.startsWith('/')
    ? searchParams.next
    : '/';

  return (
    <div className="min-h-[calc(100vh-10rem)] flex items-center justify-center py-8">
      <div className="grid w-full max-w-5xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="relative overflow-hidden rounded-[2.5rem] border border-stone-200 bg-[linear-gradient(135deg,rgba(255,183,178,0.35),rgba(232,239,232,0.55),rgba(239,237,244,0.7))] p-8 shadow-[0_24px_80px_rgba(41,37,36,0.08)]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.8),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(255,255,255,0.55),transparent_24%)]" />
          <div className="relative flex h-full flex-col justify-between gap-10">
            <div className="max-w-xl space-y-5">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/60 bg-white/55 px-3 py-1 text-xs uppercase tracking-[0.28em] text-[var(--text-muted)] backdrop-blur-sm">
                Astram access
              </div>
              <h1 className="text-4xl md:text-5xl font-light tracking-tight leading-tight text-[var(--text-main)]">
                Sign in to the incident command workspace.
              </h1>
              <p className="max-w-lg text-base leading-7 text-[var(--text-muted)]">
                Access the dashboard, planning tools, reports, and live operational views from one protected entry point.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                ['Protected', 'Session cookie with server-side redirect'],
                ['Centralized', 'One login for the full operational workspace'],
                ['Production-safe', 'HttpOnly cookie and secure flag in prod'],
              ].map(([title, text]) => (
                <div key={title} className="rounded-2xl border border-white/65 bg-white/60 p-4 backdrop-blur-sm">
                  <div className="text-sm font-semibold text-[var(--text-main)]">{title}</div>
                  <div className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{text}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <LoginScreen nextPath={nextPath} />
      </div>
    </div>
  );
}
