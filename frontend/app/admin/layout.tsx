'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Toaster } from 'sonner';
import { LayoutDashboard, UserCheck, ShieldCheck, Users, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV = [
  { href: '/admin', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/admin/waitlist', label: 'Waitlist', icon: UserCheck },
  { href: '/admin/x-verification', label: 'X Verification', icon: ShieldCheck },
  { href: '/admin/users', label: 'Users', icon: Users },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <header className="sticky top-0 z-20 border-b border-white/[0.06] bg-[#0a0a0a]/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-3">
          <Link href="/admin" className="flex items-center gap-2 group">
            <div className="h-7 w-7 rounded-md bg-[#f95400] grid place-items-center font-syne font-bold text-black text-sm leading-none">L</div>
            <div className="leading-tight">
              <div className="font-syne text-sm font-bold tracking-tight">Loudrr</div>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">Admin Console</div>
            </div>
          </Link>

          <nav className="flex items-center gap-1">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = href === '/admin' ? pathname === '/admin' : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                    active
                      ? 'bg-white/[0.08] text-white'
                      : 'text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-200'
                  )}
                >
                  <Icon size={14} />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-3 text-xs text-zinc-500">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.06] px-2.5 py-1 transition-colors hover:bg-white/[0.04] hover:text-zinc-200"
              title="FastAPI Swagger docs"
            >
              <span>API docs</span>
              <ExternalLink size={11} />
            </a>
            <a
              href="http://localhost:8000/admin"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.06] px-2.5 py-1 transition-colors hover:bg-white/[0.04] hover:text-zinc-200"
              title="SQLAdmin raw DB browser"
            >
              <span>SQLAdmin</span>
              <ExternalLink size={11} />
            </a>
            <div className="hidden md:block text-[11px] text-zinc-600">All actions audit-logged</div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>

      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          style: {
            background: '#111',
            border: '1px solid rgba(255,255,255,0.08)',
            color: '#fff',
          },
        }}
      />
    </div>
  );
}
