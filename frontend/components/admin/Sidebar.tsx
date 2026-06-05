'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SidebarItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string | number | null;
}

interface SidebarProps {
  collapsed: boolean;
  items: SidebarItem[];
  footer?: React.ReactNode;
}

export function Sidebar({ collapsed, items, footer }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        'sticky top-0 flex h-screen flex-col border-r border-white/[0.08] bg-[#0a0a0a] transition-[width] duration-200 ease-out',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center gap-2.5 border-b border-white/[0.06] px-3',
          collapsed && 'justify-center px-0'
        )}
      >
        <Image
          src="/loudrr-icon.png"
          width={28}
          height={28}
          alt="Loudrr"
          priority
          className="h-7 w-7 shrink-0 object-contain"
        />
        {!collapsed && (
          <div className="leading-tight">
            <div className="font-syne text-sm font-bold tracking-tight text-white">Loudrr</div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">Admin Console</div>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 scrollbar-content">
        <ul className="flex flex-col gap-1">
          {items.map(({ href, label, icon: Icon, badge }) => {
            const active = href === '/admin' ? pathname === '/admin' : pathname.startsWith(href);
            return (
              <li key={href}>
                <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}>
                  <Link
                    href={href}
                    title={collapsed ? label : undefined}
                    className={cn(
                      'relative flex items-center gap-3 rounded-md py-2 text-sm font-medium transition-colors',
                      collapsed ? 'justify-center px-0' : 'px-3',
                      active
                        ? 'border-l-[3px] border-l-[#f95400] bg-gradient-to-r from-[#f95400]/[0.18] via-[#f95400]/[0.06] to-transparent text-white'
                        : 'border-l-[3px] border-l-transparent text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-200'
                    )}
                  >
                    <Icon size={16} className={active ? 'text-[#f95400]' : ''} />
                    {!collapsed && (
                      <>
                        <span className="flex-1 truncate">{label}</span>
                        {badge !== undefined && badge !== null && badge !== '' && (
                          <span
                            className={cn(
                              'ml-auto inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none',
                              active
                                ? 'bg-[#f95400] text-black'
                                : 'bg-white/[0.06] text-zinc-300'
                            )}
                          >
                            {badge}
                          </span>
                        )}
                      </>
                    )}
                  </Link>
                </motion.div>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer slot */}
      {footer && (
        <div
          className={cn(
            'shrink-0 border-t border-white/[0.06] p-2',
            collapsed && 'flex flex-col items-center'
          )}
        >
          {footer}
        </div>
      )}
    </aside>
  );
}
