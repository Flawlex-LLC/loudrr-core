'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { adminApi } from '@/lib/api';

export default function AdminDashboard() {
  const [waitlistCount, setWaitlistCount] = useState<number | null>(null);
  const [xverifCount, setXverifCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([adminApi.pendingWaitlist(200), adminApi.pendingXVerifications(200)])
      .then(([w, x]) => {
        setWaitlistCount(w.length);
        setXverifCount(x.length);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-red-900 bg-red-950/50 p-4 text-sm text-red-300">
        Failed to load: {error}
        {error.startsWith('403') && (
          <div className="mt-2 text-red-200">
            You need <code className="rounded bg-black/40 px-1">admin</code> or{' '}
            <code className="rounded bg-black/40 px-1">superadmin</code> role.
            Bootstrap via <code className="rounded bg-black/40 px-1">scripts/seed_admins.py</code>.
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <DashboardCard
        href="/admin/waitlist"
        title="Pending Waitlist"
        count={waitlistCount}
        cta="Review →"
      />
      <DashboardCard
        href="/admin/x-verification"
        title="Pending X Verifications"
        count={xverifCount}
        cta="Review →"
      />
    </div>
  );
}

function DashboardCard({
  href, title, count, cta,
}: { href: string; title: string; count: number | null; cta: string }) {
  return (
    <Link
      href={href}
      className="block rounded-lg border border-zinc-800 bg-[#111] p-6 transition-colors hover:border-zinc-700 hover:bg-[#161616]"
    >
      <div className="text-sm text-zinc-400">{title}</div>
      <div className="mt-2 text-4xl font-semibold">
        {count === null ? <span className="text-zinc-700">—</span> : count}
      </div>
      <div className="mt-4 text-xs text-zinc-500">{cta}</div>
    </Link>
  );
}
