'use client';

import { useEffect, useState } from 'react';
import { adminApi, PendingWaitlistEntry } from '@/lib/api';

export default function AdminWaitlistPage() {
  const [entries, setEntries] = useState<PendingWaitlistEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setEntries(await adminApi.pendingWaitlist(200));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => { load(); }, []);

  async function act(id: string, op: 'approve' | 'reject') {
    if (op === 'reject' && !confirm('Reject this waitlist entry?')) return;
    setBusyId(id);
    try {
      if (op === 'approve') await adminApi.approveWaitlist(id);
      else await adminApi.rejectWaitlist(id, '');
      await load();
    } catch (e) {
      alert(`${op} failed: ${(e as Error).message}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-baseline justify-between">
        <h2 className="text-xl font-semibold">Pending Waitlist</h2>
        <div className="text-sm text-zinc-500">
          {entries?.length ?? '—'} pending
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-900 bg-red-950/50 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {entries === null ? (
        <div className="text-zinc-500">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="rounded-md border border-zinc-800 bg-[#111] p-8 text-center text-zinc-500">
          No pending entries.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-[#111] text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Telegram</th>
                <th className="px-4 py-3">X handle</th>
                <th className="px-4 py-3">Region / Niche</th>
                <th className="px-4 py-3">Submitted</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-zinc-800 bg-[#0d0d0d]">
                  <td className="px-4 py-3 font-mono text-xs text-zinc-300">{e.email}</td>
                  <td className="px-4 py-3">
                    {e.telegram_username ? `@${e.telegram_username}` : (
                      <span className="text-zinc-600">—</span>
                    )}
                    <div className="text-xs text-zinc-600">{e.telegram_id ?? ''}</div>
                  </td>
                  <td className="px-4 py-3">
                    {e.x_username ? `@${e.x_username}` : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-4 py-3 text-xs text-zinc-400">
                    {e.region || '—'} / {e.niche || '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-zinc-500">
                    {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      disabled={busyId === e.id}
                      onClick={() => act(e.id, 'approve')}
                      className="mr-2 rounded bg-green-700 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-green-600 disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      disabled={busyId === e.id}
                      onClick={() => act(e.id, 'reject')}
                      className="rounded bg-red-800 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
