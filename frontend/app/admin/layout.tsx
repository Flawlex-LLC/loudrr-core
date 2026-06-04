'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/admin', label: 'Dashboard' },
  { href: '/admin/waitlist', label: 'Waitlist' },
  { href: '/admin/x-verification', label: 'X Verification' },
  { href: '/admin/users', label: 'Users' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-[#1a1a1a] text-white">
      <header className="border-b border-zinc-800 bg-[#111]">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
          <h1 className="text-lg font-semibold tracking-tight">Loudrr Admin</h1>
          <nav className="flex gap-1">
            {TABS.map((t) => {
              const active = t.href === '/admin'
                ? pathname === '/admin'
                : pathname.startsWith(t.href);
              return (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                    active
                      ? 'bg-zinc-800 text-white'
                      : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                  }`}
                >
                  {t.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto text-xs text-zinc-500">
            All actions are audit-logged.
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
