'use client';

import { Suspense, useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { initTelegramWebApp, hapticFeedback } from '@/lib/telegram';

// API base URL
const API_BASE_URL = typeof window !== 'undefined' && window.location.hostname !== 'localhost'
  ? '/api/miniapp'
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/miniapp');

// Get Telegram init data
function getTelegramInitData(): string {
  if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp) {
    return (window as any).Telegram.WebApp.initData;
  }
  return '';
}

// API request helper
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getTelegramInitData();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(initData && { 'X-Telegram-Init-Data': initData }),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || error.message || 'Request failed');
  }

  return response.json();
}

interface WaitlistInfo {
  status: 'pending' | 'submitted' | 'approved';
  email?: string;
  x_username?: string;
  x_display_name?: string;
  x_avatar_url?: string;
  x_followers_count?: number;
  x_is_verified?: boolean;
  message?: string;
}

interface WaitlistCompleteResponse {
  status: 'success' | 'already_registered';
  message: string;
  email: string;
  x_username: string;
  x_display_name?: string;
  x_avatar_url?: string;
  x_followers_count?: number;
  x_is_verified?: boolean;
  // Referral preview (actual code assigned when approved)
  referral_code?: string;
  referral_link?: string;
}

type PageState = 'loading' | 'form' | 'submitting' | 'success' | 'error' | 'already_approved';

function WaitlistContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [state, setState] = useState<PageState>('loading');
  const [email, setEmail] = useState('');
  const [xUsername, setXUsername] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WaitlistCompleteResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Initialize Telegram Web App
  useEffect(() => {
    initTelegramWebApp();
  }, []);

  // Fetch entry info on mount
  useEffect(() => {
    if (!token) {
      setError('Invalid link - missing token');
      setState('error');
      return;
    }

    async function fetchInfo() {
      try {
        const info = await apiRequest<WaitlistInfo>(`/waitlist/complete/?token=${token}`);

        if (info.status === 'approved') {
          setState('already_approved');
          return;
        }

        if (info.status === 'submitted') {
          // Already submitted - show success
          setResult({
            status: 'success',
            message: 'Already on waitlist',
            email: info.email || '',
            x_username: info.x_username || '',
            x_display_name: info.x_display_name,
            x_avatar_url: info.x_avatar_url,
            x_followers_count: info.x_followers_count,
          });
          setState('success');
          return;
        }

        setEmail(info.email || '');
        setState('form');

        // Focus the input after render
        setTimeout(() => inputRef.current?.focus(), 100);
      } catch (err: any) {
        setError(err.message || 'Failed to load');
        setState('error');
      }
    }

    fetchInfo();
  }, [token]);

  // Handle form submission
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const cleanUsername = xUsername.trim().replace(/^@/, '');

    if (!cleanUsername) {
      setError('Please enter your X username');
      return;
    }

    if (!/^[a-zA-Z0-9_]{1,15}$/.test(cleanUsername)) {
      setError('Invalid X username format');
      return;
    }

    setState('submitting');
    setError(null);
    hapticFeedback('medium');

    try {
      const response = await apiRequest<WaitlistCompleteResponse>('/waitlist/complete/', {
        method: 'POST',
        body: JSON.stringify({
          token,
          x_username: cleanUsername,
        }),
      });

      setResult(response);
      setState('success');
      hapticFeedback('success');
    } catch (err: any) {
      setError(err.message || 'Registration failed');
      setState('form');
      hapticFeedback('error');
    }
  }

  // Format follower count
  function formatFollowers(count: number | undefined): string {
    if (!count) return '';
    if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
    if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
    return count.toString();
  }

  // Referral link from API response or generate preview
  const referralLink = result?.referral_link || `https://loudrr.com?ref=${(result?.x_username?.slice(0,4) || 'USER').toUpperCase()}XXXX`;

  const shareText = `I just joined the @loudrr waitlist! 🔊\n\nEarn karma by engaging. Spend karma to grow.\n\nJoin me: ${referralLink}`;

  // Copy referral link
  async function copyReferralLink() {
    try {
      await navigator.clipboard.writeText(referralLink);
      hapticFeedback('success');
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }

  // Share to X with referral link
  function shareToX() {
    const text = encodeURIComponent(shareText);
    window.open(`https://x.com/intent/tweet?text=${text}`, '_blank');
    hapticFeedback('light');
  }

  // Share to Telegram
  function shareToTelegram() {
    const url = encodeURIComponent(referralLink);
    const text = encodeURIComponent('Join me on Loudrr! Earn karma by engaging on X.');
    window.open(`https://t.me/share/url?url=${url}&text=${text}`, '_blank');
    hapticFeedback('light');
  }

  // Render based on state
  if (state === 'loading') {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <img src="/loudrr-icon.png" alt="Loudrr" className="w-16 h-16 animate-pulse" />
          <p className="text-white/60 text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <div className="text-4xl mb-4">😕</div>
          <h1 className="text-xl font-semibold text-white mb-2">Something went wrong</h1>
          <p className="text-white/60 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (state === 'already_approved') {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <div className="text-4xl mb-4">🎉</div>
          <h1 className="text-xl font-semibold text-white mb-2">You're already approved!</h1>
          <p className="text-white/60 text-sm mb-6">
            Close this and tap "Open Loudrr" to start engaging.
          </p>
        </div>
      </div>
    );
  }

  if (state === 'success' && result) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex flex-col">
        {/* Success content */}
        <div className="flex-1 flex flex-col items-center justify-center p-6">
          {/* Success card */}
          <div className="relative w-full max-w-sm bg-gradient-to-br from-[#1a1a1a] to-[#0f0f0f] rounded-2xl overflow-hidden border border-white/10">
            {/* Gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-orange-500/10 via-transparent to-purple-500/10" />

            <div className="relative p-6">
              {/* Header */}
              <div className="flex items-center gap-3 mb-6">
                <img src="/loudrr-icon.png" alt="Loudrr" className="w-10 h-10" />
                <div>
                  <h2 className="text-white font-bold text-lg">You're on the list!</h2>
                  <p className="text-white/50 text-xs">We'll notify you when approved</p>
                </div>
              </div>

              {/* User info */}
              <div className="flex items-center gap-4 bg-black/30 rounded-xl p-4">
                {result.x_avatar_url ? (
                  <img
                    src={result.x_avatar_url}
                    alt=""
                    className="w-14 h-14 rounded-full border-2 border-orange-500/50"
                  />
                ) : (
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center text-white text-xl font-bold">
                    {result.x_username?.[0]?.toUpperCase() || '?'}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-white font-semibold truncate">
                      {result.x_display_name || result.x_username}
                    </span>
                    {result.x_is_verified && (
                      <svg className="w-4 h-4 text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M22.5 12.5c0-1.58-.875-2.95-2.148-3.6.154-.435.238-.905.238-1.4 0-2.21-1.71-3.998-3.818-3.998-.47 0-.92.084-1.336.25C14.818 2.415 13.51 1.5 12 1.5s-2.816.917-3.437 2.25c-.415-.165-.866-.25-1.336-.25-2.11 0-3.818 1.79-3.818 4 0 .494.083.964.237 1.4-1.272.65-2.147 2.018-2.147 3.6 0 1.495.782 2.798 1.942 3.486-.02.17-.032.34-.032.514 0 2.21 1.708 4 3.818 4 .47 0 .92-.086 1.335-.25.62 1.334 1.926 2.25 3.437 2.25 1.512 0 2.818-.916 3.437-2.25.415.163.865.248 1.336.248 2.11 0 3.818-1.79 3.818-4 0-.174-.012-.344-.033-.513 1.158-.687 1.943-1.99 1.943-3.484zm-6.616-3.334l-4.334 6.5c-.145.217-.382.334-.625.334-.143 0-.288-.04-.416-.126l-.115-.094-2.415-2.415c-.293-.293-.293-.768 0-1.06s.768-.294 1.06 0l1.77 1.767 3.825-5.74c.23-.345.696-.436 1.04-.207.346.23.44.696.21 1.04z" />
                      </svg>
                    )}
                  </div>
                  <div className="text-white/50 text-sm">@{result.x_username}</div>
                  {result.x_followers_count && (
                    <div className="text-white/40 text-xs mt-0.5">
                      {formatFollowers(result.x_followers_count)} followers
                    </div>
                  )}
                </div>
              </div>

              {/* Email */}
              <div className="mt-4 text-center">
                <p className="text-white/40 text-xs">
                  📧 {result.email}
                </p>
              </div>
            </div>
          </div>

          {/* Share buttons - 3 side by side */}
          <div className="mt-6 w-full max-w-sm flex gap-2">
            {/* Copy Link */}
            <button
              onClick={copyReferralLink}
              className="flex-1 py-3 px-2 bg-white/5 border border-white/10 rounded-xl text-white/70 font-medium flex flex-col items-center gap-1 hover:bg-white/10 active:scale-[0.98] transition-all"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.193-9.193a4.5 4.5 0 00-6.364 0l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
              </svg>
              <span className="text-xs">Copy</span>
            </button>

            {/* Share to X */}
            <button
              onClick={shareToX}
              className="flex-1 py-3 px-2 bg-white/5 border border-white/10 rounded-xl text-white/70 font-medium flex flex-col items-center gap-1 hover:bg-white/10 active:scale-[0.98] transition-all"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
              <span className="text-xs">X</span>
            </button>

            {/* Share to Telegram */}
            <button
              onClick={shareToTelegram}
              className="flex-1 py-3 px-2 bg-white/5 border border-white/10 rounded-xl text-white/70 font-medium flex flex-col items-center gap-1 hover:bg-white/10 active:scale-[0.98] transition-all"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
              </svg>
              <span className="text-xs">Telegram</span>
            </button>
          </div>

          <p className="mt-6 text-white/40 text-xs text-center">
            We'll send you a message here when you're approved
          </p>
        </div>
      </div>
    );
  }

  // Form state
  return (
    <div className="min-h-screen bg-[#0A0A0A] flex flex-col">
      <div className="flex-1 flex flex-col p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <img src="/loudrr-icon.png" alt="Loudrr" className="w-10 h-10" />
          <div>
            <h1 className="text-white font-bold text-xl">Join Loudrr</h1>
            <p className="text-white/50 text-sm">Complete your registration</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col">
          {/* Email field (read-only) */}
          <div className="mb-4">
            <label className="block text-white/60 text-sm mb-2">Email</label>
            <input
              type="email"
              value={email}
              readOnly
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white/60 text-sm cursor-not-allowed"
            />
          </div>

          {/* X Username field */}
          <div className="mb-6">
            <label className="block text-white/60 text-sm mb-2">X Username</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-white/40">@</span>
              <input
                ref={inputRef}
                type="text"
                value={xUsername}
                onChange={(e) => setXUsername(e.target.value.replace(/[^a-zA-Z0-9_]/g, ''))}
                placeholder="yourhandle"
                maxLength={15}
                disabled={state === 'submitting'}
                className="w-full pl-9 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-white/30 text-sm focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20 transition-all disabled:opacity-50"
              />
            </div>
            {error && (
              <p className="mt-2 text-red-400 text-sm">{error}</p>
            )}
          </div>

          {/* Submit button */}
          <div className="mt-auto">
            <button
              type="submit"
              disabled={state === 'submitting' || !xUsername.trim()}
              className="w-full py-4 px-6 bg-gradient-to-r from-orange-500 to-orange-600 rounded-xl text-white font-semibold text-base shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {state === 'submitting' ? (
                <>
                  <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Joining...
                </>
              ) : (
                'Join Waitlist'
              )}
            </button>

            <p className="mt-4 text-white/40 text-xs text-center">
              By joining, you agree to our Terms of Service
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

// Loading fallback
function LoadingFallback() {
  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <img src="/loudrr-icon.png" alt="Loudrr" className="w-16 h-16 animate-pulse" />
        <p className="text-white/60 text-sm">Loading...</p>
      </div>
    </div>
  );
}

// Wrap with Suspense for useSearchParams
export default function WaitlistPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <WaitlistContent />
    </Suspense>
  );
}
