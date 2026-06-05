'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Coins,
  FileText,
  Layers,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  UserCheck,
  Users,
  Wallet,
} from 'lucide-react';
import { adminApi, type AdminStats, type AdminUserRow } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { EmptyState } from '@/components/admin/EmptyState';
import { Badge } from '@/components/admin/Badge';
import { Skeleton, TableSkeleton } from '@/components/admin/Skeleton';

// ---------- helpers ----------

function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString();
}

function fmtKarma(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec} seconds ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`;
  const diffMo = Math.round(diffDay / 30);
  if (diffMo < 12) return `${diffMo} month${diffMo === 1 ? '' : 's'} ago`;
  const diffYr = Math.round(diffMo / 12);
  return `${diffYr} year${diffYr === 1 ? '' : 's'} ago`;
}

function shortId(id: string | null | undefined): string {
  if (!id) return '—';
  // UUIDs are typically 36 chars; show first segment for compactness.
  if (id.length >= 8) return id.slice(0, 8);
  return id;
}

type AuditTone = 'success' | 'danger' | 'warning' | 'info' | 'neutral';

function actionTone(action: string): AuditTone {
  const a = action.toLowerCase();
  if (a.includes('approve') || a.includes('grant') || a.includes('unban') || a.includes('whitelist_add')) {
    return 'success';
  }
  if (a.includes('reject') || a.includes('revoke') || a.includes('ban') || a.includes('delete')) {
    return 'danger';
  }
  if (a.includes('update') || a.includes('edit') || a.includes('change')) {
    return 'warning';
  }
  if (a.includes('create') || a.includes('view') || a.includes('search')) {
    return 'info';
  }
  return 'neutral';
}

function detailSummary(detail: Record<string, unknown>): string {
  if (!detail || Object.keys(detail).length === 0) return '—';
  try {
    const json = JSON.stringify(detail);
    if (json.length <= 60) return json;
    return json.slice(0, 57) + '…';
  } catch {
    return '—';
  }
}

// ---------- component ----------

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([adminApi.getStats(), adminApi.searchUsers('', 200)])
      .then(([s, u]) => {
        if (cancelled) return;
        setStats(s);
        setUsers(u);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Map actor_id -> telegram_username (best-effort; falls back to short UUID).
  const actorMap = useMemo(() => {
    const m = new Map<string, string>();
    if (!users) return m;
    for (const u of users) {
      if (u.telegram_username) m.set(u.id, u.telegram_username);
    }
    return m;
  }, [users]);

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

  const loading = stats === null;
  const q = stats?.queues;
  const u = stats?.users;
  const c = stats?.credits;
  const p = stats?.posts;
  const e = stats?.engagements;
  const audit = stats?.recent_audit ?? [];

  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-syne text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Operational overview — pending queues, user health, karma flow, and recent admin activity.
        </p>
      </div>

      {/* ---------- Section 1: Queues ---------- */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Queues</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            label="Pending Waitlist"
            value={loading ? null : fmtInt(q?.pending_waitlist)}
            hint={q?.pending_waitlist === 0 ? 'Inbox zero' : 'Click to review'}
            icon={UserCheck}
            href="/admin/waitlist"
            tone={q && q.pending_waitlist > 0 ? 'attention' : 'default'}
          />
          <StatCard
            label="Pending X Verifications"
            value={loading ? null : fmtInt(q?.pending_x_verifications)}
            hint={q?.pending_x_verifications === 0 ? 'Inbox zero' : 'Click to review'}
            icon={ShieldCheck}
            href="/admin/x-verification"
            tone={q && q.pending_x_verifications > 0 ? 'attention' : 'default'}
          />
          <StatCard
            label="Pending Batches"
            value={loading ? null : fmtInt(q?.pending_batches)}
            hint="Awaiting processing"
            icon={Layers}
            tone={q && q.pending_batches > 0 ? 'attention' : 'default'}
          />
        </div>
      </section>

      {/* ---------- Section 2: Users ---------- */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Users</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total Users" value={loading ? null : fmtInt(u?.total)} icon={Users} />
          <StatCard
            label="Banned"
            value={loading ? null : fmtInt(u?.banned)}
            icon={AlertTriangle}
            tone={u && u.banned > 0 ? 'danger' : 'default'}
          />
          <StatCard
            label="Whitelisted"
            value={loading ? null : fmtInt(u?.whitelisted)}
            icon={CheckCircle2}
            tone={u && u.whitelisted > 0 ? 'success' : 'default'}
          />
          <StatCard
            label="X-Verified"
            value={loading ? null : fmtInt(u?.x_verified)}
            icon={ShieldCheck}
          />
        </div>

        <div className="mt-3 rounded-2xl border border-white/[0.06] bg-[#0d0d0d] px-4 py-3 text-xs text-zinc-400">
          {loading ? (
            <Skeleton className="h-4 w-2/3" />
          ) : (
            <>
              <span className="text-zinc-500">Breakdown:</span>{' '}
              <span className="text-white">Admins: {fmtInt(u?.by_role.admin)}</span>
              <span className="mx-2 text-zinc-700">•</span>
              <span className="text-white">Superadmins: {fmtInt(u?.by_role.superadmin)}</span>
              <span className="mx-2 text-zinc-700">•</span>
              <span className="text-white">Regular: {fmtInt(u?.by_role.regular)}</span>
              <span className="mx-2 text-zinc-700">•</span>
              <span className="text-white">New this week: {fmtInt(u?.new_this_week)}</span>
            </>
          )}
        </div>
      </section>

      {/* ---------- Section 3: Economy ---------- */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Economy</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            label="Karma in Circulation"
            value={loading ? null : fmtKarma(c?.in_circulation)}
            hint="Sum of all user credits"
            icon={Coins}
          />
          <StatCard
            label="Total Earned (lifetime)"
            value={loading ? null : fmtKarma(c?.total_earned)}
            icon={TrendingUp}
            tone="success"
          />
          <StatCard
            label="Total Spent (lifetime)"
            value={loading ? null : fmtKarma(c?.total_spent)}
            icon={TrendingDown}
          />
        </div>
      </section>

      {/* ---------- Section 4: Posts ---------- */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Posts</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard label="Active Posts" value={loading ? null : fmtInt(p?.active)} icon={FileText} />
          <StatCard
            label="Completed Posts"
            value={loading ? null : fmtInt(p?.completed)}
            icon={CheckCircle2}
            tone="success"
          />
          <StatCard
            label="Total Active Escrow"
            value={loading ? null : `${fmtKarma(p?.total_escrow_active)} karma`}
            hint="Across all active posts"
            icon={Wallet}
          />
        </div>
      </section>

      {/* ---------- Section 5: Engagements ---------- */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Engagements</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            label="Engagements Today"
            value={loading ? null : fmtInt(e?.today)}
            icon={Activity}
          />
          <StatCard label="This Week" value={loading ? null : fmtInt(e?.this_week)} icon={Clock} />
          <StatCard
            label="All-time Total"
            value={loading ? null : fmtInt(e?.total)}
            icon={TrendingUp}
          />
        </div>
      </section>

      {/* ---------- Section 6: Recent Admin Activity ---------- */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Recent Admin Activity
        </h2>

        {loading ? (
          <TableSkeleton rows={6} />
        ) : audit.length === 0 ? (
          <EmptyState icon={Activity} title="No recent admin activity" />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-[#0d0d0d]">
            <table className="w-full text-sm">
              <thead className="border-b border-white/[0.06] bg-white/[0.02] text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-2.5 font-medium">When</th>
                  <th className="px-4 py-2.5 font-medium">Action</th>
                  <th className="px-4 py-2.5 font-medium">Actor</th>
                  <th className="px-4 py-2.5 font-medium">Target</th>
                  <th className="px-4 py-2.5 font-medium">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {audit.slice(0, 10).map((row) => {
                  const actorName = row.actor_id ? actorMap.get(row.actor_id) : null;
                  const actorDisplay = actorName
                    ? `@${actorName}`
                    : row.actor_id
                      ? shortId(row.actor_id)
                      : 'system';
                  return (
                    <tr key={row.id} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap">
                        {relativeTime(row.created_at_iso)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={actionTone(row.action)}>{row.action}</Badge>
                      </td>
                      <td className="px-4 py-3 text-zinc-300 whitespace-nowrap">{actorDisplay}</td>
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap">
                        <span className="text-zinc-500">{row.target_type}</span>
                        {row.target_id && (
                          <>
                            <span className="mx-1 text-zinc-700">/</span>
                            <code className="rounded bg-black/40 px-1 text-xs">
                              {shortId(row.target_id)}
                            </code>
                          </>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500">
                        <code className="break-all">{detailSummary(row.detail)}</code>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
