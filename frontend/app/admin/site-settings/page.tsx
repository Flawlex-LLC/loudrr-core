'use client';

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { AlertTriangle, RefreshCcw, Search, Settings2 } from 'lucide-react';
import {
  adminApi,
  SiteSettingRow,
  SiteSettingsGroup,
} from '@/lib/api';
import { Button } from '@/components/admin/Button';
import { Modal } from '@/components/admin/Modal';
import { Input } from '@/components/admin/Input';
import { Badge } from '@/components/admin/Badge';
import { EmptyState } from '@/components/admin/EmptyState';
import { Skeleton } from '@/components/admin/Skeleton';
import { cn } from '@/lib/utils';

interface EditState {
  setting: SiteSettingRow | null;
  value: string;
}

const EMPTY_EDIT: EditState = { setting: null, value: '' };

export default function SiteSettingsPage() {
  const [groups, setGroups] = useState<SiteSettingsGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [liveOnly, setLiveOnly] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [edit, setEdit] = useState<EditState>(EMPTY_EDIT);
  const [saving, setSaving] = useState(false);

  async function load() {
    setError(null);
    try {
      const res = await adminApi.getSiteSettings();
      setGroups(res.groups);
      setLastUpdated(new Date());
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast.error('Failed to load site settings', { description: msg });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredGroups = useMemo(() => {
    if (!groups) return null;
    const q = query.trim().toLowerCase();
    return groups
      .map((g) => ({
        ...g,
        settings: g.settings.filter((s) => {
          if (liveOnly && !s.live) return false;
          if (!q) return true;
          return (
            s.key.toLowerCase().includes(q) ||
            s.description.toLowerCase().includes(q)
          );
        }),
      }))
      .filter((g) => g.settings.length > 0);
  }, [groups, query, liveOnly]);

  const totalShown = useMemo(
    () => filteredGroups?.reduce((acc, g) => acc + g.settings.length, 0) ?? 0,
    [filteredGroups],
  );

  function startEdit(setting: SiteSettingRow) {
    setEdit({ setting, value: setting.value });
  }

  function closeEdit() {
    if (saving) return;
    setEdit(EMPTY_EDIT);
  }

  async function save() {
    if (!edit.setting) return;
    const key = edit.setting.key;
    const value = edit.value.trim();
    setSaving(true);
    try {
      await adminApi.updateSiteSetting(key, value);
      toast.success(`Updated ${key}`, {
        description: edit.setting.live
          ? 'Live setting — change takes effect immediately.'
          : 'Stored. Will apply once backend code wires this setting.',
      });
      setEdit(EMPTY_EDIT);
      await load();
    } catch (e) {
      const msg = (e as Error).message;
      // Error shape: "<status>: <detail>"
      if (msg.startsWith('403')) {
        toast.error('Superadmin required', {
          description:
            'Editing site settings requires the superadmin role. Promote your account or ask a superadmin.',
        });
      } else if (msg.startsWith('422') || msg.startsWith('400')) {
        toast.error(`Invalid value for ${key}`, {
          description: msg.replace(/^\d+:\s*/, ''),
        });
      } else {
        toast.error(`Failed to update ${key}`, { description: msg });
      }
    } finally {
      setSaving(false);
    }
  }

  // ---- Render ----

  if (error && !groups) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Couldn't load site settings"
        description={
          error.startsWith('403')
            ? "You're authenticated but lack admin role. Bootstrap via backend/scripts/seed_admins.py."
            : error
        }
        action={
          <Button variant="secondary" size="sm" onClick={load}>
            <RefreshCcw size={12} />
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-syne text-2xl font-bold tracking-tight">Site Settings</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">
            Tune the karma economy, tiers, and verification policy. Edits require
            superadmin and take effect immediately for live settings.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={load} disabled={groups === null}>
          <RefreshCcw size={12} />
          Refresh
        </Button>
      </div>

      {/* Sticky filter bar */}
      <div className="sticky top-[57px] z-10 -mx-6 border-b border-white/[0.06] bg-[#0a0a0a]/85 px-6 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[260px] flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by key or description (e.g. POST_COST, decay, tier)…"
              className="w-full rounded-lg border border-white/[0.08] bg-[#0a0a0a] py-2 pl-9 pr-3 text-sm text-white placeholder:text-zinc-600 focus:border-[#f95400]/40 focus:outline-none focus:ring-1 focus:ring-[#f95400]/40"
            />
          </div>

          <label className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-[#0d0d0d] px-3 py-2 text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={liveOnly}
              onChange={(e) => setLiveOnly(e.target.checked)}
              className="h-3.5 w-3.5 accent-[#f95400]"
            />
            Show only LIVE settings
          </label>

          <div className="ml-auto text-[11px] text-zinc-600">
            {groups === null
              ? 'Loading…'
              : `Showing ${totalShown} setting${totalShown === 1 ? '' : 's'} · Last updated: ${formatLastUpdated(lastUpdated)}`}
          </div>
        </div>
      </div>

      {/* Body */}
      {groups === null ? (
        <div className="space-y-8">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-3">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-3 w-72" />
              <div className="space-y-2 pt-2">
                {Array.from({ length: 4 }).map((__, j) => (
                  <Skeleton key={j} className="h-16 w-full" />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : filteredGroups && filteredGroups.length === 0 ? (
        <EmptyState
          icon={Settings2}
          title="No settings match"
          description={
            query
              ? `Nothing matches "${query}"${liveOnly ? ' (with LIVE filter on)' : ''}. Try a broader search.`
              : liveOnly
                ? 'No live settings — toggle the filter off to see stored-but-not-yet-wired ones.'
                : 'No site settings defined. Run backend/scripts/seed_settings.py to seed defaults.'
          }
          action={
            (query || liveOnly) ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { setQuery(''); setLiveOnly(false); }}
              >
                Clear filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-10">
          {filteredGroups!.map((group) => (
            <section key={group.name} className="space-y-3">
              <div>
                <h2 className="font-syne text-lg font-semibold tracking-tight text-white">
                  {group.name}
                </h2>
                <p className="mt-0.5 text-sm text-zinc-500">{group.description}</p>
              </div>

              <div className="overflow-hidden rounded-2xl border border-white/[0.06]">
                <ul className="divide-y divide-white/[0.04]">
                  {group.settings.map((s) => (
                    <li
                      key={s.key}
                      className="flex flex-col gap-3 bg-[#111] px-4 py-3 transition-colors hover:bg-[#161616] sm:flex-row sm:items-center"
                    >
                      {/* Left: ~60% */}
                      <div className="min-w-0 flex-[3] space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <code className="font-mono text-sm text-white">{s.key}</code>
                          {s.live ? (
                            <Badge tone="success">live</Badge>
                          ) : (
                            <Badge tone="warning">stored, not yet wired</Badge>
                          )}
                          {s.value !== s.default && (
                            <span className="text-[11px] text-zinc-600">
                              default: <span className="font-mono">{s.default}</span>
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500">{s.description}</p>
                        {!s.persisted && (
                          <p className="text-[11px] text-amber-400/80">
                            (using default — not yet stored)
                          </p>
                        )}
                      </div>

                      {/* Right: ~40% — value pill */}
                      <div className="flex-[2] sm:text-right">
                        <button
                          onClick={() => startEdit(s)}
                          className={cn(
                            'inline-flex max-w-full items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-sm transition-colors',
                            'border-white/[0.08] bg-[#0a0a0a] text-zinc-100 hover:border-[#f95400]/40 hover:bg-[#1a0d05] hover:text-[#f95400]',
                          )}
                          title={`Edit ${s.key}`}
                        >
                          <span className="truncate">{s.value}</span>
                          <span className="text-[10px] uppercase tracking-wide text-zinc-600">
                            {s.data_type}
                          </span>
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Edit modal */}
      <Modal
        open={edit.setting !== null}
        onClose={closeEdit}
        title={edit.setting?.key ?? ''}
        description={edit.setting?.description}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={closeEdit} disabled={saving}>
              Cancel
            </Button>
            <Button variant="primary" loading={saving} onClick={save}>
              Save
            </Button>
          </>
        }
      >
        {edit.setting && (
          <form
            className="space-y-3 text-sm"
            onSubmit={(e) => { e.preventDefault(); void save(); }}
          >
            <div className="rounded-lg border border-white/[0.06] bg-[#0a0a0a] p-3 text-xs">
              <div className="grid grid-cols-[100px_1fr] gap-y-1.5">
                <span className="text-zinc-500">Type</span>
                <span className="font-mono text-zinc-200">{edit.setting.data_type}</span>
                <span className="text-zinc-500">Default</span>
                <span className="font-mono text-zinc-200">{edit.setting.default}</span>
                <span className="text-zinc-500">Status</span>
                <span className={cn(edit.setting.live ? 'text-emerald-400' : 'text-amber-400')}>
                  {edit.setting.live ? 'live (read by backend now)' : 'stored, not yet wired'}
                </span>
                <span className="text-zinc-500">Stored row</span>
                <span className={cn(edit.setting.persisted ? 'text-zinc-200' : 'text-amber-400')}>
                  {edit.setting.persisted ? 'yes' : 'no — will be created on save'}
                </span>
              </div>
            </div>

            {edit.setting.data_type === 'bool' ? (
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Value</label>
                <select
                  value={edit.value}
                  onChange={(e) => setEdit({ ...edit, value: e.target.value })}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#0a0a0a] px-3 py-2 text-sm text-white focus:border-[#f95400]/40 focus:outline-none focus:ring-1 focus:ring-[#f95400]/40"
                >
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
                <p className="mt-1 text-xs text-zinc-600">
                  Default: <span className="font-mono">{edit.setting.default}</span>
                </p>
              </div>
            ) : (
              <Input
                label="Value"
                value={edit.value}
                onChange={(e) => setEdit({ ...edit, value: e.target.value })}
                placeholder={edit.setting.default}
                hint={`Default: ${edit.setting.default} (${edit.setting.data_type})`}
                autoFocus
              />
            )}

            <p className="text-[11px] text-zinc-600">
              Saving requires the <span className="text-zinc-400">superadmin</span> role and is
              audit-logged. {edit.setting.live ? 'This setting is live — change applies on next request.' : 'This setting is not yet read by backend code; the value will be stored for future use.'}
            </p>
          </form>
        )}
      </Modal>
    </div>
  );
}

function formatLastUpdated(d: Date | null): string {
  if (!d) return '—';
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diffSec < 5) return 'now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return d.toLocaleTimeString();
}
