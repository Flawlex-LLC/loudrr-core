'use client';

import { useEffect, useState } from 'react';
import { UserCheck, ShieldCheck, Users, AlertTriangle } from 'lucide-react';
import { adminApi } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { EmptyState } from '@/components/admin/EmptyState';

export default function AdminDashboard() {
  const [waitlistCount, setWaitlistCount] = useState<number | null>(null);
  const [xverifCount, setXverifCount] = useState<number | null>(null);
  const [userCount, setUserCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      adminApi.pendingWaitlist(200),
      adminApi.pendingXVerifications(200),
      adminApi.searchUsers('', 200),
    ])
      .then(([w, x, u]) => {
        setWaitlistCount(w.length);
        setXverifCount(x.length);
        setUserCount(u.length);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Couldn't load dashboard"
        description={
          error.startsWith('403')
            ? "You're authenticated but lack admin role. Bootstrap via backend/scripts/seed_admins.py (sets ADMIN_TELEGRAM_IDS to superadmin)."
            : error
        }
      />
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-syne text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-500">Operational overview. Pending queues to clear and recent traffic.</p>
      </div>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Queues</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            label="Pending Waitlist"
            value={waitlistCount}
            hint={waitlistCount === 0 ? 'Inbox zero ✨' : 'Click to review'}
            icon={UserCheck}
            href="/admin/waitlist"
            tone={waitlistCount && waitlistCount > 0 ? 'attention' : 'default'}
          />
          <StatCard
            label="Pending X Verifications"
            value={xverifCount}
            hint={xverifCount === 0 ? 'Inbox zero ✨' : 'Click to review'}
            icon={ShieldCheck}
            href="/admin/x-verification"
            tone={xverifCount && xverifCount > 0 ? 'attention' : 'default'}
          />
          <StatCard
            label="Recent Users"
            value={userCount === 200 ? '200+' : userCount}
            hint="Click to search and manage"
            icon={Users}
            href="/admin/users"
          />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Tips</h2>
        <div className="rounded-2xl border border-white/[0.06] bg-[#111] p-5 text-sm text-zinc-400 space-y-2">
          <p>• <span className="text-white">Credit grant/revoke</span> uses prompted modals with audit notes — every action lands in <code className="rounded bg-black/40 px-1 text-xs">audit_logs</code>.</p>
          <p>• <span className="text-white">Revoking credits</span> requires <code className="rounded bg-black/40 px-1 text-xs">superadmin</code> role (not just admin).</p>
          <p>• Use the <a className="text-[#f95400] hover:underline" href="http://localhost:8000/admin" target="_blank" rel="noopener noreferrer">SQLAdmin</a> raw browser when you need direct table access; mutations there route through the same service-layer actions.</p>
        </div>
      </section>
    </div>
  );
}
