'use client';

import { useEffect, useState } from 'react';
import { adminApi, PendingXVerification } from '@/lib/api';

export default function AdminXVerificationPage() {
  const [rows, setRows] = useState<PendingXVerification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setRows(await adminApi.pendingXVerifications(200));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => { load(); }, []);

  async function act(id: string, op: 'approve' | 'reject') {
    const msg = op === 'approve'
      ? 'Adopt the claimed X handle and mark this user verified?'
      : 'Reject this verification request?';
    if (!confirm(msg)) return;
    setBusyId(id);
    try {
      if (op === 'approve') await adminApi.approveXVerification(id);
      else await adminApi.rejectXVerification(id, '');
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
        <h2 className="text-xl font-semibold">Pending X Verifications</h2>
        <div className="text-sm text-zinc-500">{rows?.length ?? '—'} pending</div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-900 bg-red-950/50 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {rows === null ? (
        <div className="text-zinc-500">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border border-zinc-800 bg-[#111] p-8 text-center text-zinc-500">
          No pending verifications.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-[#111] text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3">User (Telegram)</th>
                <th className="px-4 py-3">Submitted handle</th>
                <th className="px-4 py-3">Claimed (OAuth) handle</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-zinc-800 bg-[#0d0d0d]">
                  <td className="px-4 py-3">
                    {r.user_telegram_username
                      ? `@${r.user_telegram_username}`
                      : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    {r.submitted_x_username
                      ? `@${r.submitted_x_username}`
                      : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    @{r.claimed_x_username}
                  </td>
                  <td className="px-4 py-3 text-xs text-zinc-500">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      disabled={busyId === r.id}
                      onClick={() => act(r.id, 'approve')}
                      className="mr-2 rounded bg-green-700 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-green-600 disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      disabled={busyId === r.id}
                      onClick={() => act(r.id, 'reject')}
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
