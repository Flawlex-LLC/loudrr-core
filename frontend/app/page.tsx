'use client';

import { useEffect, useState, useRef } from 'react';
import { api, Post, SessionResponse, CompleteResponse, User, UserStats, SubmitPostResponse, AppSettings } from '@/lib/api';
import { initTelegramWebApp, hapticFeedback, openLink } from '@/lib/telegram';

type Tab = 'home' | 'engage' | 'campaigns' | 'earn';
type EngageState = 'idle' | 'loading' | 'ready' | 'engaging' | 'completing' | 'completed' | 'error';

// Lifted engage state - persists across tab switches
interface EngageData {
  state: EngageState;
  session: SessionResponse | null;
  currentPostIndex: number;
  engagedPosts: Set<string>;
  error: string | null;
  result: CompleteResponse | null;
  lastFetchedAt: number | null;
}

const STALE_THRESHOLD_MS = 20 * 60 * 1000; // 20 minutes

/**
 * Format karma value for display.
 *
 * DECIMAL KARMA SYSTEM:
 * - Backend stores 4 decimal places (e.g., 1.0300)
 * - Frontend displays 2 decimal places (e.g., 1.03)
 * - Whole numbers show as integers (e.g., 150.00 -> 150)
 *
 * @param value - Karma value (number with up to 4 decimal places)
 * @returns Formatted string (e.g., "150", "1.03", "1,234.56")
 */
function formatKarma(value: number): string {
  // If it's a whole number, display without decimals
  if (Number.isInteger(value)) {
    return value.toLocaleString();
  }

  // Otherwise display with 2 decimal places
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Logo loader with expanding circle from right edge to full size
function PixelLoader({ isComplete, size: sizeProp = 'default' }: { isComplete?: boolean; progress?: number; size?: 'default' | 'sm' | 'xs' }) {
  // Size variants: default=72px, sm=32px, xs=20px
  const sizeMap = { default: 72, sm: 32, xs: 20 };
  const size = sizeMap[sizeProp];
  const dotSize = Math.max(2, Math.round(size / 18)); // Scale dot size with loader size
  return (
    <div className="loader-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <style>{`
        @keyframes circle-grow-${size} {
          0% {
            width: ${dotSize}px;
            height: ${dotSize}px;
            top: calc(50% - ${dotSize / 2}px);
            right: 0;
            opacity: 0.6;
          }
          100% {
            width: ${size}px;
            height: ${size}px;
            top: 0;
            right: 0;
            opacity: 0;
          }
        }
        @keyframes logo-pulse {
          0% { opacity: 0.6; }
          50% { opacity: 1; }
          100% { opacity: 0.6; }
        }
      `}</style>
      <div style={{ position: 'relative', width: size, height: size }}>
        {/* Base logo */}
        <img
          src="/loudrr-icon.png"
          alt=""
          width={size}
          height={size}
          style={{
            width: size,
            height: size,
            display: 'block',
            animation: isComplete ? 'none' : 'logo-pulse 1.5s ease-in-out infinite',
          }}
        />
        {/* Expanding circle - masked to logo shape */}
        {!isComplete && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: size,
              height: size,
              overflow: 'hidden',
              maskImage: 'url(/loudrr-icon.png)',
              maskSize: '100% 100%',
              maskRepeat: 'no-repeat',
              WebkitMaskImage: 'url(/loudrr-icon.png)',
              WebkitMaskSize: '100% 100%',
              WebkitMaskRepeat: 'no-repeat',
            } as React.CSSProperties}
          >
            {/* Circle starts as dot on right, expands to full logo size */}
            <div
              style={{
                position: 'absolute',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0.1) 100%)',
                mixBlendMode: 'color',
                animation: `circle-grow-${size} 1.5s ease-out infinite`,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default function MiniApp() {
  const [activeTab, setActiveTab] = useState<Tab>('home');
  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [showLoader, setShowLoader] = useState(true);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [showLinkXModal, setShowLinkXModal] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  // Lifted engage state - persists across tab switches
  const [engageData, setEngageData] = useState<EngageData>({
    state: 'idle',
    session: null,
    currentPostIndex: 0,
    engagedPosts: new Set(),
    error: null,
    result: null,
    lastFetchedAt: null,
  });

  useEffect(() => {
    initTelegramWebApp();
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      setServerError(null);
      // Load user and settings in parallel
      const [userData, settingsData] = await Promise.all([
        api.getUser(),
        api.getSettings(),
      ]);
      setUser(userData);
      setSettings(settingsData);
    } catch (err) {
      console.error('Failed to load initial data:', err);
      setServerError(err instanceof Error ? err.message : 'Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  // Simulate loading progress - increases steadily, jumps to 100 when done
  useEffect(() => {
    if (!loading) {
      setLoadingProgress(100);
      return;
    }

    const interval = setInterval(() => {
      setLoadingProgress((prev) => {
        // Cap at 90% until actually loaded
        if (prev >= 90) return 90;
        return prev + 3;
      });
    }, 80);

    return () => clearInterval(interval);
  }, [loading]);

  // Hide loader after loading completes with small delay for transition
  useEffect(() => {
    if (!loading) {
      const timer = setTimeout(() => setShowLoader(false), 400);
      return () => clearTimeout(timer);
    }
  }, [loading]);

  // Auto-show Link X modal if user hasn't linked their X account
  useEffect(() => {
    if (!loading && user && !user.x_username) {
      setShowLinkXModal(true);
    }
  }, [loading, user]);

  const loadUser = async () => {
    try {
      const userData = await api.getUser();
      setUser(userData);
    } catch (err) {
      console.error('Failed to load user:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tab: Tab) => {
    hapticFeedback('light');
    setActiveTab(tab);
    // Refetch user data when switching to Home tab (for fresh available_posts count)
    if (tab === 'home') {
      loadUser();
    }
  };

  // Show pixel loader
  if (showLoader) {
    return <PixelLoader isComplete={!loading} progress={loadingProgress} />;
  }

  // Show server error screen
  if (serverError) {
    return (
      <div className="h-screen flex flex-col items-center justify-center p-6 bg-black">
        <div className="text-center max-w-sm">
          {/* Error Icon */}
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">Server Error</h2>
          <p className="text-gray-400 text-sm mb-6">
            Unable to connect to the server. Please try again later.
          </p>
          <button
            onClick={() => {
              setLoading(true);
              setShowLoader(true);
              loadInitialData();
            }}
            className="px-6 py-3 bg-[#FF6B00] text-black font-semibold rounded-xl hover:bg-[#FF8533] transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden tg-safe-area-top tg-safe-area-bottom">
      {/* Header */}
      <Header
        user={user}
        showProfileMenu={showProfileMenu}
        setShowProfileMenu={setShowProfileMenu}
        onStatsClick={() => {
          setShowProfileMenu(false);
          setShowStatsModal(true);
        }}
        onLinkX={() => setShowLinkXModal(true)}
      />

      <div className="flex-1 overflow-y-auto pb-20 pt-14 scrollbar-content">
        {activeTab === 'home' && <HomeTab user={user} onRefresh={loadUser} />}
        {activeTab === 'engage' && <EngageTab user={user} onUserUpdate={loadUser} engageData={engageData} setEngageData={setEngageData} settings={settings} />}
        {activeTab === 'campaigns' && <CampaignsTab />}
        {activeTab === 'earn' && <EarnTab />}
      </div>

      {/* Bottom Tab Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-black/90 backdrop-blur-xl border-t border-[#FF6B00]/20 px-2 py-2 tg-safe-area-bottom">
        <div className="flex justify-around items-center max-w-md mx-auto">
          <TabButton
            tabId="home"
            icon={<HomeIconFill />}
            iconOutline={<HomeIcon />}
            label="Home"
            active={activeTab === 'home'}
            onClick={() => handleTabChange('home')}
          />
          <TabButton
            tabId="engage"
            icon={<BoltIconFill />}
            iconOutline={<BoltIcon />}
            label="Engage"
            active={activeTab === 'engage'}
            onClick={() => handleTabChange('engage')}
          />
          <TabButton
            tabId="campaigns"
            icon={<MegaphoneIconFill />}
            iconOutline={<MegaphoneIcon />}
            label="Campaigns"
            active={activeTab === 'campaigns'}
            onClick={() => handleTabChange('campaigns')}
          />
          <TabButton
            tabId="earn"
            icon={<GiftIconFill />}
            iconOutline={<GiftIcon />}
            label="Earn"
            active={activeTab === 'earn'}
            onClick={() => handleTabChange('earn')}
          />
        </div>
      </div>

      {/* Stats Modal */}
      <StatsModal
        isOpen={showStatsModal}
        onClose={() => setShowStatsModal(false)}
      />

      {/* Link X Account Modal */}
      <LinkXModal
        isOpen={showLinkXModal}
        onClose={() => setShowLinkXModal(false)}
        onSuccess={(data) => {
          setUser(prev => prev ? {
            ...prev,
            x_username: data.x_username,
            tweetscout_score: data.tweetscout_score,
            x_followers_count: data.followers_count,
            x_display_name: data.display_name,
          } : null);
          setShowLinkXModal(false);
        }}
      />
    </div>
  );
}

// Tab Button Component
function TabButton({
  icon,
  iconOutline,
  label,
  active,
  onClick,
  tabId,
}: {
  icon: React.ReactNode;
  iconOutline: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  tabId: string;
}) {
  return (
    <button
      onClick={onClick}
      data-tab={tabId}
      className={`flex flex-col items-center justify-center w-20 py-2 rounded-xl transition-colors ${
        active ? 'text-[#FF6B00]' : 'text-gray-500 hover:text-gray-300'
      }`}
    >
      <div className="w-6 h-6">{active ? icon : iconOutline}</div>
      <span className={`text-xs font-medium ${active ? 'gold-gradient-text' : ''}`}>{label}</span>
    </button>
  );
}

// HEADER COMPONENT
function Header({
  user,
  showProfileMenu,
  setShowProfileMenu,
  onStatsClick,
  onLinkX,
}: {
  user: User | null;
  showProfileMenu: boolean;
  setShowProfileMenu: (show: boolean) => void;
  onStatsClick: () => void;
  onLinkX: () => void;
}) {
  const telegramUsername = user?.telegram_username || 'User';
  const xUsername = user?.x_username || null;

  return (
    <div className="fixed top-0 left-0 right-0 bg-black/90 backdrop-blur-xl border-b border-[#FF6B00]/20 z-40 tg-safe-area-top">
      <div className="flex items-center justify-between px-4 py-3">
        {/* Logo */}
        <div className="flex items-center">
          <img
            src="/loudrr-logo.png"
            alt="Loudrr"
            className="h-8 w-auto"
          />
        </div>

        {/* Profile */}
        <div className="relative">
          <button
            onClick={() => {
              hapticFeedback('light');
              setShowProfileMenu(!showProfileMenu);
            }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/60 backdrop-blur-md border border-[#FF6B00]/30 hover:border-[#FF6B00]/60 hover:bg-[#FF6B00]/10 transition-all"
          >
            <div className="w-6 h-6 rounded-full gold-gradient-bg flex items-center justify-center">
              <span className="text-xs font-bold text-black">
                {telegramUsername.charAt(0).toUpperCase()}
              </span>
            </div>
            <span className="text-sm text-gray-300 max-w-[100px] truncate">
              {telegramUsername}
            </span>
            <ChevronDownIcon className={`w-4 h-4 text-gray-400 transition-transform ${showProfileMenu ? 'rotate-180' : ''}`} />
          </button>

          {/* Profile Dropdown */}
          {showProfileMenu && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowProfileMenu(false)}
              />

              {/* Menu */}
              <div className="absolute right-0 top-full mt-2 w-64 bg-black/95 backdrop-blur-xl border border-[#FF6B00]/30 rounded-xl shadow-2xl shadow-[#FF6B00]/10 z-50 overflow-hidden slide-up">
                {/* Telegram Account */}
                <div className="px-4 py-3 border-b border-[#FF6B00]/20">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full gold-gradient-bg flex items-center justify-center">
                      <span className="text-sm font-bold text-black">
                        {telegramUsername.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-400">Telegram</p>
                      <p className="text-sm font-medium text-white truncate">@{telegramUsername}</p>
                    </div>
                  </div>
                </div>

                {/* X Account - clickable if not connected */}
                {xUsername ? (
                  <div className="px-4 py-3 border-b border-[#FF6B00]/20">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-black flex items-center justify-center">
                        <XLogoIcon className="w-5 h-5 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-gray-400">X Account</p>
                        <p className="text-sm font-medium text-white truncate">@{xUsername}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      hapticFeedback('light');
                      setShowProfileMenu(false);
                      onLinkX();
                    }}
                    className="w-full px-4 py-3 border-b border-[#FF6B00]/20 flex items-center gap-3 hover:bg-[#FF6B00]/10 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-full bg-black flex items-center justify-center">
                      <XLogoIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0 text-left">
                      <p className="text-xs text-gray-400">X Account</p>
                      <p className="text-sm text-[#FF6B00]">Link your account</p>
                    </div>
                    <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                  </button>
                )}

                {/* Discord */}
                <div className="px-4 py-3 border-b border-[#FF6B00]/20">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-black flex items-center justify-center">
                      <DiscordIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-400">Discord</p>
                      <p className="text-sm text-gray-500 italic">Coming soon</p>
                    </div>
                  </div>
                </div>

                {/* Stats Option */}
                <button
                  onClick={() => {
                    hapticFeedback('light');
                    onStatsClick();
                  }}
                  className="w-full px-4 py-3 flex items-center gap-3 hover:bg-black transition-colors"
                >
                  <div className="w-10 h-10 rounded-full bg-black flex items-center justify-center">
                    <ChartIconFill className="w-5 h-5 text-[#FF6B00]" />
                  </div>
                  <div className="flex-1 text-left">
                    <p className="text-sm font-medium text-white">Stats</p>
                    <p className="text-xs text-gray-400">View your performance</p>
                  </div>
                  <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// HOME TAB
// Helper functions for TweetScout score multiplier (web3 tier names)
function getScoreMultiplier(score: number): string {
  if (score >= 1000) return "1.35x";
  if (score >= 800) return "1.30x";
  if (score >= 600) return "1.25x";
  if (score >= 400) return "1.20x";
  if (score >= 200) return "1.15x";
  if (score >= 100) return "1.10x";
  return "1.0x";
}

function getScoreTier(score: number): string {
  if (score >= 1000) return "GOAT";
  if (score >= 800) return "OG";
  if (score >= 600) return "Legend";
  if (score >= 400) return "Based";
  if (score >= 200) return "Degen";
  if (score >= 100) return "Normie";
  return "Anon";
}

function HomeTab({ user, onRefresh }: { user: User | null; onRefresh: () => void }) {
  if (!user) {
    return (
      <div className="p-4 text-center">
        <p className="text-gray-400">Could not load user data</p>
        <button onClick={onRefresh} className="btn-primary mt-4">Retry</button>
      </div>
    );
  }

  const tweetscoutScore = user.tweetscout_score || 0;
  const scoreMultiplier = getScoreMultiplier(tweetscoutScore);
  const scoreTier = getScoreTier(tweetscoutScore);

  return (
    <div className="p-4 space-y-4">
      {/* Balance Card - High-Tech Design */}
      <div className="relative overflow-hidden rounded-2xl border border-[#FF6B00]/20 bg-gradient-to-br from-black via-zinc-900/50 to-black">
        {/* Grid Pattern Background */}
        <div className="absolute inset-0 opacity-[0.07]" style={{
          backgroundImage: `linear-gradient(#FF6B00 1px, transparent 1px), linear-gradient(90deg, #FF6B00 1px, transparent 1px)`,
          backgroundSize: '24px 24px'
        }} />

        {/* Glowing orb effects */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-[#FF6B00]/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-16 -left-16 w-32 h-32 bg-[#FF6B00]/10 rounded-full blur-3xl" />

        {/* Scan line effect */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#FF6B00]/[0.03] to-transparent" />

        <div className="relative z-10 p-6">
          {/* Header Row */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FF6B00] to-[#CC5500] flex items-center justify-center shadow-lg shadow-[#FF6B00]/20">
                <WalletIconFill className="w-5 h-5 text-black" />
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Available Balance</p>
                <p className="text-xs text-[#FF6B00]">{scoreMultiplier} earn multiplier</p>
              </div>
            </div>
            <div className="px-3 py-1.5 rounded-full bg-[#FF6B00]/10 border border-[#FF6B00]/30 backdrop-blur-sm">
              <span className="text-xs font-medium text-[#FF6B00] uppercase tracking-wide">{scoreTier}</span>
            </div>
          </div>

          {/* Main Balance Display */}
          <div className="mb-6">
            <div className="flex items-end gap-3">
              <span className="text-5xl font-bold tracking-tight gold-gradient-text">{formatKarma(user.credits)}</span>
              <span className="text-lg text-gray-500 mb-1.5 font-light">karma</span>
            </div>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 gap-3 mb-5">
            <div className="bg-white/[0.03] backdrop-blur-sm rounded-xl p-3 border border-white/[0.05]">
              <div className="flex items-center gap-2 mb-1">
                <BoltIconFill className="w-4 h-4 text-[#FF6B00]" />
                <span className="text-xs text-gray-500">Engagements</span>
              </div>
              <p className="text-xl font-semibold text-white">{user.total_engagements}</p>
            </div>
            <div className="bg-white/[0.03] backdrop-blur-sm rounded-xl p-3 border border-white/[0.05]">
              <div className="flex items-center gap-2 mb-1">
                <TrophyIconFill className="w-4 h-4 text-[#FF6B00]" />
                <span className="text-xs text-gray-500">Tweet Score</span>
              </div>
              <p className="text-xl font-semibold text-white">{Math.round(tweetscoutScore)}</p>
            </div>
          </div>

          {/* Engagement Progress */}
          <div className="bg-black/40 backdrop-blur-sm rounded-xl p-4 border border-white/[0.05]">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-[#FF6B00]/10 flex items-center justify-center">
                  <BoltIcon className="w-3.5 h-3.5 text-[#FF6B00]" />
                </div>
                <span className="text-sm text-gray-400">Today's Progress</span>
              </div>
              <span className="text-sm font-mono text-white">
                {user.engaged_today || 0}
                <span className="text-gray-500">/{(user.engaged_today || 0) + (user.available_posts || 0)}</span>
              </span>
            </div>
            <div className="h-2 bg-black/60 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#FF6B00] to-[#FF8533] rounded-full transition-all duration-500 relative overflow-hidden"
                style={{
                  width: `${((user.engaged_today || 0) + (user.available_posts || 0)) > 0
                    ? ((user.engaged_today || 0) / ((user.engaged_today || 0) + (user.available_posts || 0))) * 100
                    : 0}%`
                }}
              >
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full animate-[shimmer_2s_infinite]" />
              </div>
            </div>
            {(user.available_posts || 0) > 0 ? (
              <p className="text-xs text-gray-500 mt-2">{user.available_posts} posts waiting for you</p>
            ) : (
              <p className="text-xs text-[#FF6B00] mt-2">All caught up! Check back later</p>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => {
            hapticFeedback('light');
            const engageTab = document.querySelector('[data-tab="engage"]') as HTMLButtonElement;
            if (engageTab) engageTab.click();
          }}
          className="group relative overflow-hidden rounded-xl bg-gradient-to-br from-[#FF6B00] to-[#CC5500] p-4 text-left transition-transform active:scale-[0.98]"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
          <BoltIconFill className="w-6 h-6 text-black mb-2" />
          <p className="text-sm font-semibold text-black">Start Engaging</p>
          <p className="text-xs text-black/60">Earn karma now</p>
        </button>
        <button
          onClick={() => {
            hapticFeedback('light');
            const campaignsTab = document.querySelector('[data-tab="campaigns"]') as HTMLButtonElement;
            if (campaignsTab) campaignsTab.click();
          }}
          className="group relative overflow-hidden rounded-xl bg-white/[0.03] border border-white/[0.08] p-4 text-left transition-all hover:border-[#FF6B00]/30 active:scale-[0.98]"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#FF6B00]/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
          <MegaphoneIconFill className="w-6 h-6 text-[#FF6B00] mb-2" />
          <p className="text-sm font-semibold text-white">Campaigns</p>
          <p className="text-xs text-gray-500">Coming soon</p>
        </button>
      </div>

      {/* Streak Card */}
      <StreakCard currentStreak={user.current_streak} />
    </div>
  );
}

// STREAK CARD COMPONENT - Gamified Design
function StreakCard({ currentStreak }: { currentStreak: number }) {
  const [showInfo, setShowInfo] = useState(false);

  // Get current day of week (0 = Sunday, 1 = Monday, ..., 6 = Saturday)
  const today = new Date().getDay();
  // Convert to Mon-Sun format (0 = Monday, 6 = Sunday)
  const todayMonBased = today === 0 ? 6 : today - 1;

  // Calculate which days of the week the user has engaged
  const daysEngaged = Math.min(currentStreak, todayMonBased + 1);

  const weekDays = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.02] p-4">
      {/* Info Button - Top Right */}
      <button
        onClick={() => {
          hapticFeedback('light');
          setShowInfo(!showInfo);
        }}
        className="absolute top-3 right-3 w-5 h-5 rounded-full bg-white/[0.05] flex items-center justify-center hover:bg-white/[0.1] transition-colors z-10"
      >
        <span className="text-[10px] text-gray-500 font-medium">i</span>
      </button>

      {/* Tooltip - Shows on click */}
      {showInfo && (
        <div className="absolute top-10 right-3 w-48 p-2.5 rounded-lg bg-black/95 border border-white/10 shadow-xl z-20 slide-up">
          <p className="text-[10px] text-gray-400 leading-relaxed">
            Engage daily to build streaks. Missing a day resets to 0. Rewards coming soon!
          </p>
        </div>
      )}

      {/* Header Row */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`relative w-10 h-10 rounded-xl flex items-center justify-center ${
          currentStreak > 0
            ? 'bg-gradient-to-br from-orange-500 to-red-600 shadow-lg shadow-orange-500/20'
            : 'bg-gray-800'
        }`}>
          <FireIconFill className={`w-5 h-5 ${currentStreak > 0 ? 'text-yellow-300' : 'text-gray-600'}`} />
          {currentStreak > 0 && (
            <div className="absolute inset-0 rounded-xl bg-orange-500/30 blur-md -z-10" />
          )}
        </div>
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className={`text-2xl font-bold ${currentStreak > 0 ? 'text-white' : 'text-gray-500'}`}>
              {currentStreak}
            </span>
            <span className="text-sm text-gray-500">day streak</span>
          </div>
        </div>
      </div>

      {/* Day Progress - Gamified Pills */}
      <div className="flex gap-1.5">
        {weekDays.map((day, index) => {
          const isCompleted = index < daysEngaged;
          const isToday = index === todayMonBased;
          const isFuture = index > todayMonBased;

          return (
            <div key={index} className="flex-1 flex flex-col items-center gap-1">
              <div className={`w-full h-8 rounded-lg flex items-center justify-center transition-all ${
                isCompleted
                  ? 'bg-gradient-to-b from-orange-500 to-orange-600 shadow-sm shadow-orange-500/30'
                  : isToday
                  ? 'bg-orange-500/20 border border-orange-500/40 border-dashed'
                  : isFuture
                  ? 'bg-white/[0.02]'
                  : 'bg-white/[0.04]'
              }`}>
                {isCompleted ? (
                  <CheckIcon className="w-4 h-4 text-white" />
                ) : isToday ? (
                  <div className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
                ) : null}
              </div>
              <span className={`text-[9px] font-medium ${
                isCompleted ? 'text-orange-400' : isToday ? 'text-orange-400/70' : 'text-gray-600'
              }`}>
                {day}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// CAMPAIGNS TAB (Coming Soon)
function CampaignsTab() {
  return (
    <div className="p-4 flex flex-col items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-sm">
        <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-[#FF6B00]/20 to-[#CC5500]/20 border border-[#FF6B00]/30 flex items-center justify-center">
          <MegaphoneIconFill className="w-12 h-12 text-[#FF6B00]/60" />
        </div>
        <h2 className="text-2xl font-bold mb-2 gold-gradient-text">Campaigns</h2>
        <p className="text-gray-400 mb-4">
          XP reward campaigns will be available here.
        </p>
        <div className="px-4 py-2 rounded-full bg-[#FF6B00]/10 border border-[#FF6B00]/20">
          <span className="text-sm text-[#FF6B00] font-medium">Coming Soon</span>
        </div>
      </div>
    </div>
  );
}

// EARN TAB (Coming Soon)
function EarnTab() {
  return (
    <div className="p-4 flex flex-col items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-sm">
        <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-[#FF6B00]/20 to-[#CC5500]/20 border border-[#FF6B00]/30 flex items-center justify-center">
          <GiftIconFill className="w-12 h-12 text-[#FF6B00]/60" />
        </div>
        <h2 className="text-2xl font-bold mb-2 gold-gradient-text">Earn Rewards</h2>
        <p className="text-gray-400 mb-4">
          Participate in giveaways and burn karma for rewards.
        </p>
        <div className="px-4 py-2 rounded-full bg-[#FF6B00]/10 border border-[#FF6B00]/20">
          <span className="text-sm text-[#FF6B00] font-medium">Coming Soon</span>
        </div>
      </div>
    </div>
  );
}

// ENGAGE TAB
function EngageTab({
  user,
  onUserUpdate,
  engageData,
  setEngageData,
  settings,
}: {
  user: User | null;
  onUserUpdate: () => void;
  engageData: EngageData;
  setEngageData: React.Dispatch<React.SetStateAction<EngageData>>;
  settings: AppSettings | null;
}) {
  // Extract state from lifted engageData
  const { state, session, currentPostIndex, engagedPosts, error, result, lastFetchedAt } = engageData;

  // Helper to update specific fields
  const updateEngageData = (updates: Partial<EngageData>) => {
    setEngageData(prev => ({ ...prev, ...updates }));
  };

  // Local state (not persisted across tab switches)
  const [clickedPost, setClickedPost] = useState<string | null>(null);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [likeIntentEnabled, setLikeIntentEnabled] = useState(true); // Default ON
  const [refreshing, setRefreshing] = useState(false);

  // Refs
  const carouselRef = useRef<HTMLDivElement>(null);
  const clickedPostRef = useRef<string | null>(null);
  const sessionRef = useRef<SessionResponse | null>(null);
  const engagedPostsRef = useRef<Set<string>>(new Set());
  const currentPostIndexRef = useRef(0);
  const isScrollingRef = useRef(false); // Flag to disable onScroll during programmatic scroll

  // Check if posts are stale (20+ minutes old)
  const isStale = lastFetchedAt && (Date.now() - lastFetchedAt > STALE_THRESHOLD_MS);
  const showMandatoryRefresh = state === 'ready' && isStale && !refreshing;

  // Helper to extract tweet ID and construct like intent URL
  const getLikeIntentUrl = (post: Post): string => {
    // Use tweet_id if available, otherwise extract from URL
    let tweetId = post.tweet_id;
    if (!tweetId) {
      // Extract from URL pattern: x.com/user/status/123456789 or twitter.com/user/status/123456789
      const match = post.x_link.match(/(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)/);
      tweetId = match?.[1] || '';
    }
    if (tweetId) {
      return `https://twitter.com/intent/like?tweet_id=${tweetId}`;
    }
    // Fallback to original URL if can't extract tweet ID
    return post.x_link;
  };

  // Get the appropriate URL based on like intent toggle
  const getEngageUrl = (post: Post): string => {
    return likeIntentEnabled ? getLikeIntentUrl(post) : post.x_link;
  };

  // Keep refs in sync with state
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    engagedPostsRef.current = engagedPosts;
  }, [engagedPosts]);

  // NOTE: currentPostIndexRef is the MAX ALLOWED scroll position (first unengaged post)
  // It should NOT sync with currentPostIndex state (which is the visual position)
  // Only update it on: session start, return from X engagement

  // NOTE: Removed auto-scroll useEffect - all scrolling is now handled explicitly:
  // - handleEngageClick: scrolls to next card on click
  // - startSession: scrolls to first unengaged card on load
  // - handleReturn: scrolls to next card when returning from X
  // This avoids race conditions between multiple scroll triggers.

  // Auto-detect return from X and advance to first unengaged card
  useEffect(() => {
    if (state !== 'engaging') return;

    const handleReturn = () => {
      // User returned from X - use ref to get current clickedPost value
      const postId = clickedPostRef.current;
      if (!postId) return;

      // Mark post as engaged (DB already confirmed in handleEngageClick)
      const newEngaged = new Set(engagedPostsRef.current).add(postId);
      engagedPostsRef.current = newEngaged;

      // Clear clicked state
      clickedPostRef.current = null;
      setClickedPost(null);

      // Find first unengaged post
      const posts = sessionRef.current?.posts || [];
      let nextIndex = posts.length; // Default to claim card
      for (let i = 0; i < posts.length; i++) {
        if (!newEngaged.has(posts[i].id)) {
          nextIndex = i;
          break;
        }
      }

      // Update state using lifted state setter
      currentPostIndexRef.current = nextIndex;
      setEngageData(prev => ({
        ...prev,
        state: 'ready',
        engagedPosts: newEngaged,
        currentPostIndex: nextIndex,
      }));

      // FORCE SCROLL after DOM updates (fixes race condition)
      // Disable onScroll handler to prevent it from snapping back
      isScrollingRef.current = true;
      setTimeout(() => {
        if (carouselRef.current) {
          const container = carouselRef.current;
          const cardWidth = container.offsetWidth * 0.8;
          const spacer = container.offsetWidth * 0.1;
          const targetScroll = spacer + (nextIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
          container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'smooth' });
        }
        hapticFeedback('success');
        // Re-enable onScroll after scroll animation completes
        setTimeout(() => {
          isScrollingRef.current = false;
        }, 400);
      }, 50);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        handleReturn();
      }
    };

    // Also listen for focus - handles desktop browser tab switching
    const handleFocus = () => {
      handleReturn();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [state, setEngageData]);

  const startSession = async () => {
    try {
      updateEngageData({ state: 'loading', error: null, result: null });

      const data = await api.startSession();

      // Check if user has 10+ pending engagements - show verification immediately
      if (data.show_verification) {
        const pendingSet = new Set(data.pending_post_ids || []);
        engagedPostsRef.current = pendingSet;
        currentPostIndexRef.current = data.posts.length;
        updateEngageData({
          session: data,
          state: 'ready',
          engagedPosts: pendingSet,
          currentPostIndex: data.posts.length,
          lastFetchedAt: Date.now(),
        });
        return;
      }

      if (data.posts.length > 0) {
        // Use pending_post_ids to restore user's progress (persists across sessions!)
        const pendingSet = new Set(data.pending_post_ids || []);
        engagedPostsRef.current = pendingSet;

        // Find first unengaged post (fresh posts are first in array)
        let firstUnengagedIndex = 0;
        for (let i = 0; i < data.posts.length; i++) {
          if (!pendingSet.has(data.posts[i].id)) {
            firstUnengagedIndex = i;
            break;
          }
          // If all posts are pending, go to last post + 1 (check back later)
          if (i === data.posts.length - 1) {
            firstUnengagedIndex = data.posts.length;
          }
        }

        currentPostIndexRef.current = firstUnengagedIndex;
        updateEngageData({
          session: data,
          state: 'ready',
          engagedPosts: pendingSet,
          currentPostIndex: firstUnengagedIndex,
          lastFetchedAt: Date.now(),
        });

        // Scroll to first unengaged card after DOM renders
        if (firstUnengagedIndex > 0) {
          requestAnimationFrame(() => {
            const container = carouselRef.current;
            if (container) {
              const cardWidth = container.offsetWidth * 0.8;
              const spacerWidth = container.offsetWidth * 0.1;
              const targetScroll = spacerWidth + (firstUnengagedIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
              container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'instant' });
            }
          });
        }
      } else {
        updateEngageData({
          session: data,
          state: 'completed',
          engagedPosts: new Set(),
          currentPostIndex: 0,
          result: {
            success: true,
            message: data.message || 'No posts available right now',
            credits_awarded: 0,
          },
          lastFetchedAt: Date.now(),
        });
      }
    } catch (err) {
      updateEngageData({
        state: 'error',
        error: err instanceof Error ? err.message : 'Failed to start session',
      });
    }
  };

  // Handler for mandatory refresh
  const handleMandatoryRefresh = async () => {
    setRefreshing(true);
    await startSession();
    setRefreshing(false);
  };

  const handleEngageClick = async (post: Post) => {
    // No session_token needed - engagements are tracked at user level
    if (engagedPosts.has(post.id)) return;

    try {
      hapticFeedback('light');
      await api.recordClick(post.id);

      // Mark as engaged IMMEDIATELY
      const newEngaged = new Set(engagedPosts).add(post.id);
      engagedPostsRef.current = newEngaged;

      // Find next unengaged card
      const posts = session?.posts || [];
      let nextIndex = posts.length;
      for (let i = 0; i < posts.length; i++) {
        if (!newEngaged.has(posts[i].id)) {
          nextIndex = i;
          break;
        }
      }

      // Update refs
      currentPostIndexRef.current = nextIndex;

      // Direct DOM scroll - no React state dependency
      const container = carouselRef.current;
      if (container) {
        const cardWidth = container.offsetWidth * 0.8;
        const spacerWidth = container.offsetWidth * 0.1;
        const targetScroll = spacerWidth + (nextIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
        container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'smooth' });
      }

      // Update React state for UI (checkmarks, counter)
      setEngageData(prev => ({
        ...prev,
        engagedPosts: newEngaged,
        currentPostIndex: nextIndex,
      }));

      // Open link immediately - scroll already started via DOM
      hapticFeedback('success');
      openLink(getEngageUrl(post));
    } catch (err) {
      updateEngageData({ error: err instanceof Error ? err.message : 'Failed to record click' });
    }
  };

  // Advance to next card with animation
  const advanceToNextCard = (callback?: () => void) => {
    const nextIndex = currentPostIndex + 1;
    if (nextIndex < (session?.posts?.length || 0)) {
      updateEngageData({ currentPostIndex: nextIndex });
      callback?.();
    } else {
      // All posts done - complete the session
      completeSession();
    }
  };

  const completeSession = async () => {
    // No session_token needed - verification is at user level

    try {
      updateEngageData({ state: 'completing' });
      hapticFeedback('medium');

      const data = await api.completeSession();

      // Update engagedPosts based on remaining pending engagements from server
      // This includes failed verifications that need re-engagement
      let newEngagedPosts = new Set<string>();
      if (data.pending_post_ids && data.pending_post_ids.length > 0) {
        newEngagedPosts = new Set(data.pending_post_ids);
      }
      engagedPostsRef.current = newEngagedPosts;

      updateEngageData({
        state: 'completed',
        engagedPosts: newEngagedPosts,
        result: data,
      });
      onUserUpdate();

      if (data.success && data.credits_awarded > 0) {
        hapticFeedback('success');
      }
    } catch (err) {
      updateEngageData({
        state: 'error',
        error: err instanceof Error ? err.message : 'Failed to complete session',
      });
      hapticFeedback('error');
    }
  };

  const currentPost = session?.posts?.[currentPostIndex];
  // Progress is based on engaged posts (persists across sessions), not current feed position
  const progress = (engagedPosts.size / 10) * 100;

  // Mandatory refresh popup - shown when posts are 20+ minutes old
  if (showMandatoryRefresh) {
    return (
      <div className="p-4 flex flex-col items-center justify-center min-h-[60vh]">
        <div className="card-base p-6 text-center max-w-sm">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[#FF6B00]/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-[#FF6B00]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </div>
          <h3 className="text-xl font-bold mb-2">Posts Outdated</h3>
          <p className="text-gray-400 mb-6">
            Your posts are more than 20 minutes old. Refresh to see the latest available posts.
          </p>
          <button
            onClick={handleMandatoryRefresh}
            disabled={refreshing}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {refreshing ? (
              <>
                <PixelLoader size="xs" />
                Refreshing...
              </>
            ) : (
              'Refresh Posts'
            )}
          </button>
        </div>
      </div>
    );
  }

  // Idle state
  if (state === 'idle') {
    return (
      <>
        <div className="p-4 flex flex-col items-center justify-center min-h-[60vh]">
          <div className="text-center max-w-sm">
            <div className="w-24 h-24 mx-auto mb-6 rounded-full gold-gradient-bg flex items-center justify-center glow-gold pulse-gold">
              <BoltIconFill className="w-12 h-12 text-black" />
            </div>
            <h2 className="text-2xl font-bold mb-2 gold-gradient-text">Ready to Engage?</h2>
            <p className="text-gray-400 mb-8">
              Engage with posts to earn karma. Each engagement takes about 30 seconds.
            </p>
            <button onClick={startSession} className="btn-primary w-full text-lg py-4">
              Start Engaging
            </button>
            <button
              onClick={() => {
                hapticFeedback('light');
                setShowSubmitModal(true);
              }}
              className="btn-secondary w-full mt-3 flex items-center justify-center gap-2"
            >
              <PlusIconFill className="w-5 h-5" />
              Submit Your Post
            </button>
          </div>
        </div>
        <SubmitModal
          isOpen={showSubmitModal}
          onClose={() => setShowSubmitModal(false)}
          user={user}
          onUserUpdate={onUserUpdate}
          settings={settings}
        />
      </>
    );
  }

  // Loading state
  if (state === 'loading') {
    return (
      <div className="p-4 flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <PixelLoader size="sm" />
          <p className="text-gray-400 mt-4">Finding posts...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (state === 'error') {
    return (
      <div className="p-4 flex items-center justify-center min-h-[60vh]">
        <div className="text-center max-w-sm">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-black/50 border border-[#FF6B00]/30 flex items-center justify-center">
            <XIconFill className="w-10 h-10 text-[#FF6B00]" />
          </div>
          <h2 className="text-xl font-bold mb-2">Something went wrong</h2>
          <p className="text-gray-400 mb-6">{error}</p>
          <button onClick={startSession} className="btn-primary w-full">Try Again</button>
        </div>
      </div>
    );
  }

  // Engaging state - user is on X, will auto-advance when they return
  if (state === 'engaging') {
    return (
      <div className="p-4 flex items-center justify-center min-h-[60vh]">
        <div className="text-center max-w-sm">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full gold-gradient-bg pulse-gold glow-gold flex items-center justify-center">
            <XLogoIcon className="w-10 h-10 text-black" />
          </div>
          <h2 className="text-xl font-bold mb-2">Engaging on X...</h2>
          <p className="text-gray-400 text-sm">Like & reply to the post, then return here</p>
        </div>
      </div>
    );
  }

  // Completing state
  if (state === 'completing') {
    return (
      <div className="p-4 flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <PixelLoader size="sm" />
          <p className="text-gray-400 mt-4">Verifying engagements...</p>
        </div>
      </div>
    );
  }

  // Completed state
  if (state === 'completed') {
    const isRetryRequired = result?.retry_required;
    const hasWarning = result?.warning;
    const hasPenalty = (result?.penalty_applied || 0) > 0;

    return (
      <>
        <div className="p-4 flex items-center justify-center min-h-[60vh]">
          <div className="text-center max-w-sm slide-up">
            {isRetryRequired ? (
              // Retry required - verification failed first time
              <>
                <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-yellow-500/20 border border-yellow-500/50 flex items-center justify-center">
                  <InfoIconFill className="w-12 h-12 text-yellow-500" />
                </div>
                <h2 className="text-xl font-bold mb-2">Verification Failed</h2>
                <p className="text-gray-400 mb-4">Please engage with the posts on X (like + reply) and try again.</p>
                {hasWarning && (
                  <p className="text-sm text-yellow-500 mb-4">
                    Warning: Your honesty score dropped to {result?.honesty_score || 9}
                  </p>
                )}
                <button onClick={completeSession} className="btn-primary w-full">
                  Verify Again
                </button>
              </>
            ) : hasPenalty ? (
              // Failed with penalty
              <>
                <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-red-500/20 border border-red-500/50 flex items-center justify-center">
                  <InfoIconFill className="w-12 h-12 text-red-500" />
                </div>
                <h2 className="text-xl font-bold mb-2">Verification Failed</h2>
                <p className="text-gray-400 mb-2">{result?.message}</p>
                <p className="text-sm text-red-400 mb-4">
                  -{result?.penalty_applied} karma penalty. Honesty score: {result?.honesty_score}
                </p>
                <button onClick={startSession} className="btn-primary w-full">
                  Try Again
                </button>
              </>
            ) : result?.success && result.credits_awarded > 0 ? (
              // Success
              <>
                <div className="w-28 h-28 mx-auto mb-6 rounded-full gold-gradient-bg flex items-center justify-center glow-gold">
                  <CheckIconFill className="w-14 h-14 text-black" />
                </div>
                <h2 className="text-4xl font-bold gold-gradient-text stat-glow mb-2">+{formatKarma(result.credits_awarded)}</h2>
                <p className="text-xl text-gray-300 mb-2">Karma Earned!</p>
                {result.passed !== undefined && result.failed !== undefined && result.failed > 0 && (
                  <p className="text-sm text-gray-400 mb-4">
                    {result.passed} verified, {result.failed} need re-engagement
                  </p>
                )}
                <button onClick={startSession} className="btn-primary w-full">
                  Engage More
                </button>
              </>
            ) : (
              // No credits / other
              <>
                <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-black/50 border border-[#FF6B00]/30 flex items-center justify-center">
                  <InfoIconFill className="w-12 h-12 text-[#FF6B00]" />
                </div>
                <h2 className="text-xl font-bold mb-2">{result?.message || 'Session Complete'}</h2>
                <p className="text-gray-400 mb-8">Check back later for more posts</p>
                <button onClick={startSession} className="btn-primary w-full">
                  Try Again
                </button>
              </>
            )}
            {!isRetryRequired && (
              <button
                onClick={() => {
                  hapticFeedback('light');
                  setShowSubmitModal(true);
                }}
                className="btn-secondary w-full mt-3 flex items-center justify-center gap-2"
              >
                <PlusIconFill className="w-5 h-5" />
                Submit Your Post
              </button>
            )}
          </div>
        </div>
        <SubmitModal
          isOpen={showSubmitModal}
          onClose={() => setShowSubmitModal(false)}
          user={user}
          onUserUpdate={onUserUpdate}
          settings={settings}
        />
      </>
    );
  }

  // Ready state - show current post
  return (
    <>
      <div className="p-4">
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-bold">Engage</h2>
            <span className="text-sm text-[#FF6B00]">{engagedPosts.size}/10 queued</span>
          </div>
          <div className="progress-bar h-2">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-gray-500 mt-1">Post {currentPostIndex + 1} of {session?.posts?.length || 0}</p>

          {/* Like Intent Toggle */}
          <div className="flex items-center justify-between mt-3 p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="flex items-center gap-2">
              <HeartIconFill className="w-4 h-4 text-[#FF6B00]" />
              <span className="text-sm text-gray-300">Quick Like</span>
            </div>
            <button
              onClick={() => {
                hapticFeedback('light');
                setLikeIntentEnabled(!likeIntentEnabled);
              }}
              className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
                likeIntentEnabled ? 'bg-[#FF6B00]' : 'bg-gray-600'
              }`}
            >
              <span
                className={`absolute left-0 top-1 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-200 ${
                  likeIntentEnabled ? 'translate-x-[24px]' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Card Carousel */}
        <div className="relative overflow-hidden">
          <div
            ref={carouselRef}
            className="flex gap-3 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2"
            onScroll={(e) => {
              // Skip if programmatic scrolling is in progress
              if (isScrollingRef.current) return;

              const container = e.currentTarget;
              const cardWidth = container.offsetWidth * 0.8;
              const newIndex = Math.round((container.scrollLeft - container.offsetWidth * 0.1) / cardWidth);
              // maxAllowedIndex tracks the furthest position (first unengaged post)
              // This should NOT decrease when user scrolls back to view engaged posts
              const maxAllowedIndex = currentPostIndexRef.current;

              if (newIndex > maxAllowedIndex) {
                // Block forward scroll - immediately snap back (no animation = feels like a wall)
                isScrollingRef.current = true;
                const spacerWidth = container.offsetWidth * 0.1;
                const targetScroll = spacerWidth + (maxAllowedIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
                container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'instant' });
                setTimeout(() => { isScrollingRef.current = false; }, 50);
              } else if (newIndex >= 0) {
                // Allow scrolling backward to view engaged posts
                // Only update visual state, NOT the max allowed index ref
                updateEngageData({ currentPostIndex: newIndex });
              }
            }}
          >
            {/* Left spacer for centering first card */}
            <div className="flex-shrink-0 w-[10%]" />

            {session?.posts?.map((post, index) => {
              const isCenter = index === currentPostIndex;
              const isEngaged = engagedPosts.has(post.id);
              const canAccess = index <= currentPostIndex || isEngaged;

              return (
                <div
                  key={post.id}
                  className={`snap-center flex-shrink-0 transition-all duration-300 w-[80%] ${
                    isCenter
                      ? 'scale-100 opacity-100'
                      : isEngaged
                        ? 'scale-95 opacity-70'  // Engaged but not center - slightly brighter
                        : 'scale-95 opacity-50'   // Not engaged, not center - dimmer
                  }`}
                  onClick={() => {
                    if (isCenter) {
                      if (isEngaged) {
                        // Already engaged - just open X link (no new click recorded)
                        hapticFeedback('light');
                        openLink(getEngageUrl(post));
                      } else {
                        // Not engaged - record click and open
                        handleEngageClick(post);
                      }
                    } else if (canAccess) {
                      updateEngageData({ currentPostIndex: index });
                    }
                  }}
                >
                  <div className={`card-gold p-5 min-h-[160px] relative cursor-pointer transition-all flex flex-col justify-start ${
                    isCenter ? 'ring-2 ring-[#FF6B00]/50' : ''
                  }`}>
                    {/* Top right icons */}
                    <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
                      <XLogoIcon className="w-5 h-5 text-gray-400" />
                      <ExternalLinkIconFill className="w-5 h-5 text-[#FF6B00]" />
                    </div>

                    {/* Card content */}
                    <div className="flex flex-col gap-3">
                      {/* Author header */}
                      <div className="flex items-center gap-3">
                        {/* Profile picture with engaged indicator */}
                        <div className="relative flex-shrink-0">
                          {(post.tweet_author_avatar || post.creator_avatar) ? (
                            <img
                              src={post.tweet_author_avatar || post.creator_avatar}
                              alt={post.tweet_author_name || post.creator}
                              className={`w-12 h-12 rounded-full object-cover ${
                                isEngaged ? 'ring-2 ring-[#FF6B00]/50' : ''
                              }`}
                            />
                          ) : (
                            <div className={`w-12 h-12 rounded-full gold-gradient-bg flex items-center justify-center ${
                              isEngaged ? 'ring-2 ring-[#FF6B00]/50' : ''
                            }`}>
                              <span className="text-lg font-bold text-black">
                                {(post.tweet_author_username || post.creator_x_username || post.creator).charAt(0).toUpperCase()}
                              </span>
                            </div>
                          )}
                          {/* Small tick on profile for engaged posts */}
                          {isEngaged && (
                            <div className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-[#FF6B00] flex items-center justify-center border-2 border-black">
                              <CheckIconFill className="w-3 h-3 text-black" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-white truncate">
                              {post.tweet_author_name || post.creator}
                            </p>
                            {post.is_sponsored && (
                              <span className="badge text-xs flex-shrink-0">+XP</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {(post.tweet_author_username || post.creator_x_username) && (
                              <p className="text-sm text-gray-400">
                                @{post.tweet_author_username || post.creator_x_username}
                              </p>
                            )}
                            {(post.tweet_created_at || post.created_at) && (
                              <span className="text-xs text-gray-500">
                                {new Date(post.tweet_created_at || post.created_at!).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Tweet text */}
                      {post.tweet_text && (
                        <p className="text-sm text-gray-200 line-clamp-3 leading-relaxed">
                          {post.tweet_text}
                        </p>
                      )}

                      {/* Media preview */}
                      {post.tweet_media && post.tweet_media.length > 0 && (
                        <div className="flex gap-1 mt-1">
                          {post.tweet_media.slice(0, 2).map((url, i) => (
                            <img
                              key={i}
                              src={url}
                              alt=""
                              className="h-16 w-auto rounded-md object-cover max-w-[50%]"
                            />
                          ))}
                          {post.tweet_media.length > 2 && (
                            <div className="h-16 px-3 rounded-md bg-gray-800 flex items-center justify-center">
                              <span className="text-xs text-gray-400">+{post.tweet_media.length - 2}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Expiry indicator */}
                      {post.hours_remaining !== undefined && (
                        <div className="text-xs text-gray-500 mt-auto pt-2 flex items-center gap-1">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          {post.hours_remaining > 1
                            ? `${Math.round(post.hours_remaining)}h left`
                            : post.hours_remaining > 0
                              ? `${Math.round(post.hours_remaining * 60)}m left`
                              : 'Expiring soon'
                          }
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Right spacer for centering last card */}
            <div className="flex-shrink-0 w-[10%]" />
          </div>

          {/* Scroll indicators */}
          <div className="flex justify-center gap-1.5 mt-3">
            {session?.posts?.map((_, index) => (
              <div
                key={index}
                className={`h-1.5 rounded-full transition-all ${
                  index === currentPostIndex
                    ? 'w-6 bg-[#FF6B00]'
                    : index < currentPostIndex
                      ? 'w-1.5 bg-[#FF6B00]/50'
                      : 'w-1.5 bg-gray-600'
                }`}
              />
            ))}
          </div>

          {/* Claim Rewards Button - always visible, active when 10+ engagements */}
          <button
            onClick={() => {
              if (engagedPosts.size >= 10) {
                hapticFeedback('medium');
                completeSession();
              } else {
                hapticFeedback('error');
              }
            }}
            disabled={engagedPosts.size < 10}
            className={`mt-4 w-full py-3 px-6 rounded-xl font-semibold text-lg transition-all flex items-center justify-center gap-2 ${
              engagedPosts.size >= 10
                ? 'gold-gradient-bg text-black shadow-lg shadow-[#FF6B00]/30 hover:shadow-[#FF6B00]/50 btn-glossy'
                : 'bg-white/10 text-white/40 cursor-not-allowed'
            }`}
          >
            <BoltIconFill className="w-5 h-5" />
            {engagedPosts.size >= 10
              ? `Claim ${engagedPosts.size} Rewards`
              : `${engagedPosts.size}/10 to Claim`
            }
          </button>
        </div>
      </div>

      {/* Floating Submit Button */}
      <button
        onClick={() => {
          hapticFeedback('light');
          setShowSubmitModal(true);
        }}
        className="fixed bottom-24 right-4 w-14 h-14 rounded-full gold-gradient-bg flex items-center justify-center shadow-lg shadow-[#FF6B00]/30 z-10 hover:shadow-[#FF6B00]/50 transition-all"
      >
        <PlusIconFill className="w-7 h-7 text-black" />
      </button>

      <SubmitModal
        isOpen={showSubmitModal}
        onClose={() => setShowSubmitModal(false)}
        user={user}
        onUserUpdate={onUserUpdate}
        settings={settings}
      />
    </>
  );
}

// SUBMIT MODAL
function SubmitModal({
  isOpen,
  onClose,
  user,
  onUserUpdate,
  settings,
}: {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onUserUpdate: () => void;
  settings: AppSettings | null;
}) {
  const [xLink, setXLink] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitPostResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Karma amount defaults to minimum (settings?.post_cost_min or fallback 20)
  const minCost = settings?.post_cost_min ?? 20;
  const maxCost = settings?.post_cost_max ?? 40;
  const [karmaAmount, setKarmaAmount] = useState(minCost);

  // Reset karmaAmount when modal opens or settings change
  useEffect(() => {
    if (isOpen) {
      setKarmaAmount(minCost);
    }
  }, [isOpen, minCost]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!xLink.trim() || submitting) return;

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      hapticFeedback('medium');
      const response = await api.submitPost(xLink.trim(), karmaAmount);
      setResult(response);
      setXLink('');
      onUserUpdate();
      hapticFeedback('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit post');
      hapticFeedback('error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!submitting) {
      setXLink('');
      setResult(null);
      setError(null);
      setKarmaAmount(minCost);
      onClose();
    }
  };

  const canSubmit = user && user.credits >= karmaAmount;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg bg-black/95 backdrop-blur-xl border-t border-x border-[#FF6B00]/20 rounded-t-3xl max-h-[85vh] flex flex-col animate-slide-up frosted">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-[#FF6B00]/40" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-4 pb-4 border-b border-[#FF6B00]/15">
          <div>
            <h2 className="text-xl font-bold">Submit Post</h2>
            <p className="text-gray-400 text-sm">Share your X post to get engagements</p>
          </div>
          <button
            onClick={handleClose}
            className="w-8 h-8 rounded-full bg-black/50 flex items-center justify-center"
          >
            <XIconFill className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Karma Budget Slider */}
          <div className="card p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Karma Budget</p>
                <p className="text-2xl font-bold gold-gradient-text">{formatKarma(karmaAmount)}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">Your Balance</p>
                <p className={`text-xl font-bold ${canSubmit ? 'gold-gradient-text' : 'text-gray-500'}`}>
                  {formatKarma(user?.credits || 0)}
                </p>
              </div>
            </div>

            {/* Slider */}
            <div className="space-y-2">
              <input
                type="range"
                min={minCost}
                max={maxCost}
                step={1}
                value={karmaAmount}
                onChange={(e) => {
                  hapticFeedback('light');
                  setKarmaAmount(Number(e.target.value));
                }}
                className="w-full h-2 bg-black/50 rounded-full appearance-none cursor-pointer accent-[#FF6B00] [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#FF6B00] [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-[#FF6B00]/30"
                disabled={submitting}
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>{minCost} min</span>
                <span>{maxCost} max</span>
              </div>
            </div>

            <p className="text-xs text-gray-500 text-center">
              Higher budget = more engagements on your post
            </p>
          </div>

          {/* Submit Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">X Post Link</label>
              <input
                type="url"
                value={xLink}
                onChange={(e) => setXLink(e.target.value)}
                placeholder="https://x.com/username/status/..."
                className="input-field"
                disabled={submitting}
              />
            </div>

            {error && (
              <div className="bg-black/50 border border-[#FF6B00]/30 rounded-xl p-4">
                <p className="text-[#FF6B00] text-sm">{error}</p>
              </div>
            )}

            {result?.success && (
              <div className="bg-black/50 border border-[#FF6B00]/50 rounded-xl p-4">
                <p className="text-[#FF6B00] text-sm">{result.message}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={!canSubmit || !xLink.trim() || submitting}
              className={`btn-primary w-full py-4 text-lg ${
                (!canSubmit || !xLink.trim() || submitting) ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {submitting ? 'Submitting...' : `Submit Post (${formatKarma(karmaAmount)} karma)`}
            </button>
          </form>

          {!canSubmit && user && (
            <div className="card-gold p-4">
              <p className="text-sm text-gray-300">
                You need <span className="gold-gradient-text font-semibold">{formatKarma(karmaAmount - user.credits)} more karma</span> to submit a post.
                Engage with posts to earn karma!
              </p>
            </div>
          )}

          {/* How it works */}
          <div className="space-y-3 pb-4">
            <h3 className="text-sm font-semibold text-gray-400">How it works</h3>
            <div className="space-y-2">
              {[
                `You set your karma budget (${minCost}-${maxCost})`,
                'Other users engage with your post',
                'They earn ~1 karma per engagement until your budget is depleted',
              ].map((text, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-black/50 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs gold-gradient-text">{i + 1}</span>
                  </div>
                  <p className="text-sm text-gray-400">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// STATS MODAL
function StatsModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadStats();
    }
  }, [isOpen]);

  const loadStats = async () => {
    try {
      setLoading(true);
      const data = await api.getUserStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const maxCredits = Math.max(stats?.user.total_credits_earned || 0, stats?.user.total_credits_spent || 0, 1);
  const earnedHeight = stats ? (stats.user.total_credits_earned / maxCredits) * 100 : 0;
  const spentHeight = stats ? (stats.user.total_credits_spent / maxCredits) * 100 : 0;

  const maxEngagements = Math.max(stats?.engagements.given || 0, stats?.engagements.received || 0, 1);
  const givenHeight = stats ? (stats.engagements.given / maxEngagements) * 100 : 0;
  const receivedHeight = stats ? (stats.engagements.received / maxEngagements) * 100 : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg bg-black/95 backdrop-blur-xl border-t border-x border-[#FF6B00]/20 rounded-t-3xl max-h-[85vh] flex flex-col animate-slide-up frosted">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-[#FF6B00]/40" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-4 pb-4 border-b border-[#FF6B00]/15">
          <div>
            <h2 className="text-xl font-bold">Your Stats</h2>
            <p className="text-gray-400 text-sm">Lifetime performance overview</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-black/50 flex items-center justify-center"
          >
            <XIconFill className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <PixelLoader size="sm" />
            </div>
          ) : error || !stats ? (
            <div className="text-center py-12">
              <p className="text-gray-400 mb-4">{error || 'Could not load stats'}</p>
              <button onClick={loadStats} className="btn-primary">Retry</button>
            </div>
          ) : (
            <>
              {/* Karma Flow & Engagements - Side by Side */}
              <div className="grid grid-cols-2 gap-3">
                {/* Karma Flow */}
                <div className="card-gold p-4 relative overflow-hidden">
                  <div className="relative z-10">
                    <h3 className="text-xs font-semibold text-gray-400 mb-3">Karma Flow</h3>
                    <div className="flex items-end justify-center gap-4 h-20 mb-2">
                      <div className="flex flex-col items-center">
                        <div className="w-8 stats-bar h-14 flex items-end">
                          <div
                            className="w-full stats-bar-fill"
                            style={{ height: `${earnedHeight}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-1">Earned</p>
                        <p className="text-sm font-bold gold-gradient-text">{formatKarma(stats.user.total_credits_earned)}</p>
                      </div>
                      <div className="flex flex-col items-center">
                        <div className="w-8 stats-bar h-14 flex items-end">
                          <div
                            className="w-full stats-bar-fill opacity-60"
                            style={{ height: `${spentHeight}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-1">Spent</p>
                        <p className="text-sm font-bold text-gray-300">{formatKarma(stats.user.total_credits_spent)}</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Engagements */}
                <div className="card p-4">
                  <h3 className="text-xs font-semibold text-gray-400 mb-3">Engagements</h3>
                  <div className="flex items-end justify-center gap-4 h-20 mb-2">
                    <div className="flex flex-col items-center">
                      <div className="w-8 stats-bar h-14 flex items-end">
                        <div
                          className="w-full stats-bar-fill"
                          style={{ height: `${givenHeight}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-1">Given</p>
                      <p className="text-sm font-bold gold-gradient-text">{stats.engagements.given}</p>
                    </div>
                    <div className="flex flex-col items-center">
                      <div className="w-8 stats-bar h-14 flex items-end">
                        <div
                          className="w-full stats-bar-fill"
                          style={{ height: `${receivedHeight}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-1">Received</p>
                      <p className="text-sm font-bold gold-gradient-text">{stats.engagements.received}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Posts Stats */}
              <div className="card p-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-4">Your Posts</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold gold-gradient-text">{stats.posts.total}</p>
                    <p className="text-xs text-gray-400">Total</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold gold-gradient-text">{stats.posts.active}</p>
                    <p className="text-xs text-gray-400">Active</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-400">{stats.posts.completed}</p>
                    <p className="text-xs text-gray-400">Completed</p>
                  </div>
                </div>
              </div>

              {/* Recent Posts */}
              {stats.recent_posts.length > 0 && (
                <div className="space-y-3 pb-4">
                  <h3 className="text-sm font-semibold text-gray-400">Recent Posts</h3>
                  {stats.recent_posts.map((post) => (
                    <div key={post.id} className="card p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`badge-outline ${
                          post.status === 'active' ? '' : 'opacity-60'
                        }`}>
                          {post.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(post.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-300 truncate mb-2">{post.x_link}</p>
                      <div className="progress-bar h-1">
                        <div className="progress-fill" style={{ width: `${post.engagement_progress}%` }} />
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {post.engagement_progress}% complete - {formatKarma(post.escrow_remaining)} karma remaining
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// LINK X ACCOUNT MODAL
interface LinkXResult {
  x_username: string;
  tweetscout_score: number;
  tier: string;
  followers_count: number;
  display_name: string;
}

function LinkXModal({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (data: LinkXResult) => void;
}) {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!username.trim()) {
      setError('Please enter your X username');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await api.linkXAccount(username);
      hapticFeedback('success');
      onSuccess(result);
    } catch (err: any) {
      setError(err.message || 'Failed to link account');
      hapticFeedback('error');
    } finally {
      setLoading(false);
    }
  };

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setUsername('');
      setError('');
      setLoading(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop - no onClick, can't dismiss */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative w-full max-w-sm bg-zinc-900/95 backdrop-blur-xl rounded-2xl border border-[#FF6B00]/30 p-6 animate-slide-up">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <XLogoIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Link X Account</h2>
            <p className="text-xs text-gray-400">Required to continue</p>
          </div>
        </div>

        <p className="text-sm text-gray-400 mb-4">
          Enter your X username to verify post ownership and display your mindshare score.
        </p>

        {/* Input */}
        <div className="relative mb-4">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">@</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value.replace(/[@\s]/g, ''))}
            placeholder="username"
            className="w-full bg-black/50 border border-gray-700 rounded-xl py-3 pl-8 pr-4 text-white placeholder-gray-500 focus:border-[#FF6B00]/50 focus:outline-none transition-colors"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !loading) {
                handleSubmit();
              }
            }}
          />
        </div>

        {error && (
          <p className="text-sm text-red-400 mb-4">{error}</p>
        )}

        {/* Single button - no cancel option */}
        <button
          onClick={handleSubmit}
          disabled={loading || !username.trim()}
          className="w-full py-3 rounded-xl bg-[#FF6B00] text-black font-semibold disabled:opacity-50 hover:bg-[#E56000] transition-colors"
        >
          {loading ? 'Verifying...' : 'Link Account'}
        </button>
      </div>
    </div>
  );
}

// FILLED ICONS
function HomeIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.47 3.84a.75.75 0 011.06 0l8.69 8.69a.75.75 0 101.06-1.06l-8.689-8.69a2.25 2.25 0 00-3.182 0l-8.69 8.69a.75.75 0 001.061 1.06l8.69-8.69z" />
      <path d="M12 5.432l8.159 8.159c.03.03.06.058.091.086v6.198c0 1.035-.84 1.875-1.875 1.875H15a.75.75 0 01-.75-.75v-4.5a.75.75 0 00-.75-.75h-3a.75.75 0 00-.75.75V21a.75.75 0 01-.75.75H5.625a1.875 1.875 0 01-1.875-1.875v-6.198a2.29 2.29 0 00.091-.086L12 5.43z" />
    </svg>
  );
}

function HomeIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
    </svg>
  );
}

function BoltIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M14.615 1.595a.75.75 0 01.359.852L12.982 9.75h7.268a.75.75 0 01.548 1.262l-10.5 11.25a.75.75 0 01-1.272-.71l1.992-7.302H3.75a.75.75 0 01-.548-1.262l10.5-11.25a.75.75 0 01.913-.143z" clipRule="evenodd" />
    </svg>
  );
}

function BoltIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

function PlusIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zM12.75 9a.75.75 0 00-1.5 0v2.25H9a.75.75 0 000 1.5h2.25V15a.75.75 0 001.5 0v-2.25H15a.75.75 0 000-1.5h-2.25V9z" clipRule="evenodd" />
    </svg>
  );
}

function PlusIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ChartIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.375 2.25c-1.035 0-1.875.84-1.875 1.875v15.75c0 1.035.84 1.875 1.875 1.875h.75c1.035 0 1.875-.84 1.875-1.875V4.125c0-1.036-.84-1.875-1.875-1.875h-.75zM9.75 8.625c0-1.036.84-1.875 1.875-1.875h.75c1.036 0 1.875.84 1.875 1.875v11.25c0 1.035-.84 1.875-1.875 1.875h-.75a1.875 1.875 0 01-1.875-1.875V8.625zM3 13.125c0-1.036.84-1.875 1.875-1.875h.75c1.036 0 1.875.84 1.875 1.875v6.75c0 1.035-.84 1.875-1.875 1.875h-.75A1.875 1.875 0 013 19.875v-6.75z" />
    </svg>
  );
}

function ChartIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function WalletIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M2.273 5.625A4.483 4.483 0 015.25 4.5h13.5c1.141 0 2.183.425 2.977 1.125A3 3 0 0018.75 3H5.25a3 3 0 00-2.977 2.625zM2.273 8.625A4.483 4.483 0 015.25 7.5h13.5c1.141 0 2.183.425 2.977 1.125A3 3 0 0018.75 6H5.25a3 3 0 00-2.977 2.625zM5.25 9a3 3 0 00-3 3v6a3 3 0 003 3h13.5a3 3 0 003-3v-6a3 3 0 00-3-3H15a.75.75 0 00-.75.75 2.25 2.25 0 01-4.5 0A.75.75 0 009 9H5.25z" />
    </svg>
  );
}

function FireIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12.963 2.286a.75.75 0 00-1.071-.136 9.742 9.742 0 00-3.539 6.177A7.547 7.547 0 016.648 6.61a.75.75 0 00-1.152.082A9 9 0 1015.68 4.534a7.46 7.46 0 01-2.717-2.248zM15.75 14.25a3.75 3.75 0 11-7.313-1.172c.628.465 1.35.81 2.133 1a5.99 5.99 0 011.925-3.545 3.75 3.75 0 013.255 3.717z" clipRule="evenodd" />
    </svg>
  );
}

function TrophyIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M5.166 2.621v.858c-1.035.148-2.059.33-3.071.543a.75.75 0 00-.584.859 6.753 6.753 0 006.138 5.6 6.73 6.73 0 002.743 1.346A6.707 6.707 0 019.279 15H8.54c-1.036 0-1.875.84-1.875 1.875V19.5h-.75a2.25 2.25 0 00-2.25 2.25c0 .414.336.75.75.75h15a.75.75 0 00.75-.75 2.25 2.25 0 00-2.25-2.25h-.75v-2.625c0-1.036-.84-1.875-1.875-1.875h-.739a6.706 6.706 0 01-1.112-3.173 6.73 6.73 0 002.743-1.347 6.753 6.753 0 006.139-5.6.75.75 0 00-.585-.858 47.077 47.077 0 00-3.07-.543V2.62a.75.75 0 00-.658-.744 49.22 49.22 0 00-6.093-.377c-2.063 0-4.096.128-6.093.377a.75.75 0 00-.657.744zm0 2.629c0 1.196.312 2.32.857 3.294A5.266 5.266 0 013.16 5.337a45.6 45.6 0 012.006-.343v.256zm13.5 0v-.256c.674.1 1.343.214 2.006.343a5.265 5.265 0 01-2.863 3.207 6.72 6.72 0 00.857-3.294z" clipRule="evenodd" />
    </svg>
  );
}

function CheckIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
    </svg>
  );
}

function HeartIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.645 20.91l-.007-.003-.022-.012a15.247 15.247 0 01-.383-.218 25.18 25.18 0 01-4.244-3.17C4.688 15.36 2.25 12.174 2.25 8.25 2.25 5.322 4.714 3 7.688 3A5.5 5.5 0 0112 5.052 5.5 5.5 0 0116.313 3c2.973 0 5.437 2.322 5.437 5.25 0 3.925-2.438 7.111-4.739 9.256a25.175 25.175 0 01-4.244 3.17 15.247 15.247 0 01-.383.219l-.022.012-.007.004-.003.001a.752.752 0 01-.704 0l-.003-.001z" />
    </svg>
  );
}

function XIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clipRule="evenodd" />
    </svg>
  );
}

function ExternalLinkIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M15.75 2.25H21a.75.75 0 01.75.75v5.25a.75.75 0 01-1.5 0V4.81l-8.97 8.97a.75.75 0 01-1.06-1.06l8.97-8.97h-3.44a.75.75 0 010-1.5zm-10.5 4.5a1.5 1.5 0 00-1.5 1.5v10.5a1.5 1.5 0 001.5 1.5h10.5a1.5 1.5 0 001.5-1.5V10.5a.75.75 0 011.5 0v8.25a3 3 0 01-3 3H5.25a3 3 0 01-3-3V8.25a3 3 0 013-3h8.25a.75.75 0 010 1.5H5.25z" clipRule="evenodd" />
    </svg>
  );
}

function InfoIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 01.67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 11-.671-1.34l.041-.022zM12 9a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
    </svg>
  );
}

function InfoIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
    </svg>
  );
}

function CheckIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function XLogoIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function ChevronDownIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function ChevronRightIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

function ClockIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function DiscordIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" />
    </svg>
  );
}

function SparklesIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M9 4.5a.75.75 0 01.721.544l.813 2.846a3.75 3.75 0 002.576 2.576l2.846.813a.75.75 0 010 1.442l-2.846.813a3.75 3.75 0 00-2.576 2.576l-.813 2.846a.75.75 0 01-1.442 0l-.813-2.846a3.75 3.75 0 00-2.576-2.576l-2.846-.813a.75.75 0 010-1.442l2.846-.813A3.75 3.75 0 007.466 7.89l.813-2.846A.75.75 0 019 4.5zM18 1.5a.75.75 0 01.728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 010 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 01-1.456 0l-.258-1.036a2.625 2.625 0 00-1.91-1.91l-1.036-.258a.75.75 0 010-1.456l1.036-.258a2.625 2.625 0 001.91-1.91l.258-1.036A.75.75 0 0118 1.5zM16.5 15a.75.75 0 01.712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 010 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 01-1.422 0l-.395-1.183a1.5 1.5 0 00-.948-.948l-1.183-.395a.75.75 0 010-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0116.5 15z" clipRule="evenodd" />
    </svg>
  );
}

function CalendarIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  );
}

function MegaphoneIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M16.881 4.346A23.112 23.112 0 018.25 6H7.5a5.25 5.25 0 00-.88 10.427 21.593 21.593 0 001.378 3.94c.464 1.004 1.674 1.32 2.582.796l.657-.379c.88-.508 1.165-1.592.772-2.468a17.116 17.116 0 01-.628-1.607c1.918.258 3.76.75 5.5 1.446A21.727 21.727 0 0018 11.25c0-2.413-.393-4.735-1.119-6.904zM18.26 3.74a23.22 23.22 0 011.24 7.51 23.22 23.22 0 01-1.24 7.51c-.055.161-.111.322-.17.482a.75.75 0 101.409.516 24.555 24.555 0 001.415-6.43 2.992 2.992 0 00.836-2.078c0-.806-.319-1.54-.836-2.078a24.65 24.65 0 00-1.415-6.43.75.75 0 10-1.409.516c.059.16.116.321.17.483z" />
    </svg>
  );
}

function MegaphoneIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 01-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 018.835 2.535M10.34 6.66a23.847 23.847 0 008.835-2.535m0 0A23.74 23.74 0 0018.795 3m.38 1.125a23.91 23.91 0 011.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 001.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 010 3.46" />
    </svg>
  );
}

function GiftIconFill({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9.375 3a1.875 1.875 0 000 3.75h1.875v4.5H3.375A1.875 1.875 0 011.5 9.375v-.75c0-1.036.84-1.875 1.875-1.875h3.193A3.375 3.375 0 0112 2.753a3.375 3.375 0 015.432 3.997h3.193c1.035 0 1.875.84 1.875 1.875v.75c0 1.036-.84 1.875-1.875 1.875H12.75v-4.5h1.875a1.875 1.875 0 10-1.875-1.875V6.75h-1.5V4.875C11.25 3.839 10.41 3 9.375 3zM11.25 12.75H3v6.75a2.25 2.25 0 002.25 2.25h6v-9zM12.75 12.75v9h6a2.25 2.25 0 002.25-2.25v-6.75h-8.25z" />
    </svg>
  );
}

function GiftIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 11.25v8.25a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 109.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1114.625 7.5H12m0 0V21m-8.625-9.75h18c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125h-18c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
    </svg>
  );
}
