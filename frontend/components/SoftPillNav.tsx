"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';

export const SoftPillNav = () => {
  const pathname = usePathname();
  const router = useRouter();

  if (pathname === '/login') {
    return null;
  }

  const links = [
    { href: '/', label: 'Dashboard' },
    { href: '/command-center', label: 'Command Center' },
    { href: '/field-op', label: 'Field HUD' },
    { href: '/predict', label: 'Predict' },
    { href: '/plan', label: 'Plan' },
    { href: '/planned-impact', label: 'Planned Impact' },
    { href: '/reports', label: 'Reports' },
  ];

  const signOut = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  };

  return (
    <nav className="fixed top-6 left-4 right-4 z-40 flex items-center justify-between px-6 py-3 rounded-full bg-white/70 backdrop-blur-xl border border-white/50 shadow-sm max-w-5xl mx-auto">
      <Link href="/" className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-[var(--accent-coral)]" />
        <span className="font-semibold text-[var(--text-main)] hidden sm:block">Astram</span>
      </Link>
      
      <div className="flex gap-4 font-['Outfit'] text-[var(--text-main)] text-sm overflow-x-auto no-scrollbar">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`px-3 py-1.5 rounded-full transition-colors whitespace-nowrap ${
              pathname === link.href ? 'bg-stone-100 font-medium' : 'hover:bg-stone-50'
            }`}
          >
            {link.label}
          </Link>
        ))}
        <button
          type="button"
          onClick={signOut}
          className="px-3 py-1.5 rounded-full transition-colors whitespace-nowrap hover:bg-stone-50 text-[var(--text-muted)]"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
};
