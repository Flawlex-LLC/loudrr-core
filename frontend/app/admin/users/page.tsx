'use client';

import { useEffect, useState } from 'react';
import { adminApi, AdminUserRow } from '@/lib/api';

export default function AdminUsersPage() {
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState<AdminUserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load(q: string) {
    setError(null);
    try {
      setRows(await adminApi.searchUsers(q, 100));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // initial load — most recent users
  useEffect(() => { load(''); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await load(query);
  }

  async function ban(u: AdminUserRow) {
    const reason = prompt(`Ban @${u.telegram_username || u.x_username}? Optional reason:`);
    if (reason === null) return;
    setBusyId(u.id);
    try {
      await adminApi.banUser(u.id, reason);
      await load(query);
    } catch (e) { alert(`Ban failed: ${(e as Error).message}`); }
    finally { setBusyId(null); }
  }

  async function unban(u: AdminUserRow) {
    if (!confirm(`Unban @${u.telegram_username || u.x_username}?`)) return;
    setBusyId(u.id);
    try {
      await adminApi.unbanUser(u.id);
      await load(query);
    } catch (e) { alert(`Unban failed: ${(e as Error).message}`); }
    finally { setBusyId(null); }
  }

  async function grant(u: AdminUserRow) {
    const raw = prompt(`Grant credits to @${u.telegram_username || u.x_username}\nAmount (positive number):`);
    if (!raw) return;
    const amount = parseFloat(raw);
    if (!isFinite(amount) || amount <= 0) { alert('Amount must be a positive number'); return; }
    const description = prompt('Description (optional):') ?? '';
    setBusyId(u.id);
    try {
      await adminApi.grantCredits(u.id, amount, description);
      await load(query);
    } catch (e) { alert(`Grant failed: ${(e as Error).message}`); }
    finally { setBusyId(null); }
  }

  async function revoke(u: AdminUserRow) {
    const raw = prompt(
      `Revoke credits from @${u.telegram_username || u.x_username}\n` +
      `(Requires superadmin role.)\nAmount (positive number):`
    );
    if (!raw) return;
    const amount = parseFloat(raw);
    if (!isFinite(amount) || amount <= 0) { alert('Amount must be a positive number'); return; }
    const reason = prompt('Reason (optional):') ?? '';
    setBusyId(u.id);
    try {
      await adminApi.revokeCredits(u.id, amount, reason);
      await load(query);
    } catch (e) { alert(`Revoke failed: ${(e as Error).message}`); }
    finally { setBusyId(null); }
  }

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Users</h2>

      <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by telegram_username or x_username (substring)…"
          className="flex-1 rounded-md border border-zinc-800 bg-[#0d0d0d] px-3 py-2 text-sm placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
        />
        <button
          type="submit"
          className="rounded-md bg-zinc-200 px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-white"
        >
          Search
        </button>
      </form>

      {error && (
        <div className="mb-4 rounded-md border border-red-900 bg-red-950/50 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {rows === null ? (
        <div className="text-zinc-500">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border border-zinc-800 bg-[#111] p-8 text-center text-zinc-500">
          No users found.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-[#111] text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3">Telegram</th>
                <th className="px-4 py-3">X handle</th>
                <th className="px-4 py-3">Credits</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Flags</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.id} className="border-t border-zinc-800 bg-[#0d0d0d]">
                  <td className="px-4 py-3">
                    {u.telegram_username ? `@${u.telegram_username}` : <span className="text-zinc-600">—</span>}
                    <div className="text-xs text-zinc-600">{u.telegram_id ?? ''}</div>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    {u.x_username ? `@${u.x_username}` : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-200">
                    {u.credits.toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    {u.role ? (
                      <span className={`rounded px-2 py-0.5 text-xs ${
                        u.role === 'superadmin'
                          ? 'bg-purple-900 text-purple-200'
                          : 'bg-blue-900 text-blue-200'
                      }`}>{u.role}</span>
                    ) : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {u.is_banned && <span className="mr-1 rounded bg-red-900 px-1.5 py-0.5 text-red-200">banned</span>}
                    {u.is_whitelisted && <span className="mr-1 rounded bg-amber-900 px-1.5 py-0.5 text-amber-200">whitelisted</span>}
                    {u.x_verified && <span className="rounded bg-emerald-900 px-1.5 py-0.5 text-emerald-200">x-verified</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex gap-1">
                      <button
                        disabled={busyId === u.id}
                        onClick={() => grant(u)}
                        className="rounded bg-green-700 px-2 py-1 text-xs font-medium text-white hover:bg-green-600 disabled:opacity-50"
                      >Grant</button>
                      <button
                        disabled={busyId === u.id}
                        onClick={() => revoke(u)}
                        className="rounded bg-orange-800 px-2 py-1 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-50"
                        title="Requires superadmin"
                      >Revoke</button>
                      {u.is_banned ? (
                        <button
                          disabled={busyId === u.id}
                          onClick={() => unban(u)}
                          className="rounded bg-zinc-700 px-2 py-1 text-xs font-medium text-white hover:bg-zinc-600 disabled:opacity-50"
                        >Unban</button>
                      ) : (
                        <button
                          disabled={busyId === u.id}
                          onClick={() => ban(u)}
                          className="rounded bg-red-800 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                        >Ban</button>
                      )}
                    </div>
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
