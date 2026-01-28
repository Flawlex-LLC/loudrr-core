'use client';

import { useEffect, useState, useRef } from 'react';
import { api, Post, SessionResponse, CompleteResponse, User, UserStats, SubmitPostResponse, AppSettings, ClaimBatch, ClaimHistoryResponse, loudApi, LoudProject, LoudProjectsResponse, LoudSubmitResponse, LoudLeaderboardResponse, normalizeXLink } from '@/lib/api';
import { initTelegramWebApp, hapticFeedback, openLink } from '@/lib/telegram';
import { BorderBeam } from '@/components/ui/border-beam';
import ShimmerButton from '@/components/ui/shimmer-button';
import AnimatedGradientText from '@/components/ui/animated-gradient';

type Tab = 'home' | 'engage' | 'campaigns' | 'earn' | 'loud';
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
  // Queue-based claim history (like spot trading)
  claimHistory: ClaimBatch[];
  hasProcessingBatch: boolean;
  isClaimLoading: boolean;
}

const STALE_THRESHOLD_MS = 20 * 60 * 1000; // 20 minutes

// Orange gradient style for icons
const ICON_GRADIENT_STYLE = {
  background: 'linear-gradient(135deg, #FF9500 0%, #f95400 50%, #CC5500 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text'
} as React.CSSProperties;

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
  const [comingSoonToast, setComingSoonToast] = useState<string | null>(null);
  const [toastVisible, setToastVisible] = useState(false);
  const comingSoonTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showComingSoonToast = (message: string) => {
    if (comingSoonTimeoutRef.current) clearTimeout(comingSoonTimeoutRef.current);
    setComingSoonToast(message);
    setToastVisible(true);
    // Short display, then fade up and out
    comingSoonTimeoutRef.current = setTimeout(() => {
      setToastVisible(false);
      setTimeout(() => setComingSoonToast(null), 400);
    }, 1500);
  };

  // Lifted engage state - persists across tab switches
  const [engageData, setEngageData] = useState<EngageData>({
    state: 'idle',
    session: null,
    currentPostIndex: 0,
    engagedPosts: new Set(),
    error: null,
    result: null,
    lastFetchedAt: null,
    claimHistory: [],
    hasProcessingBatch: false,
    isClaimLoading: false,
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
            className="px-6 py-3 bg-[#f95400] text-black font-semibold rounded-xl hover:bg-[#ff7020] transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show onboarding screen for new whitelisted users (tweetscout_score == 0)
  if (user && user.is_whitelisted && (user.tweetscout_score === 0 || user.tweetscout_score === undefined) && user.x_username) {
    return (
      <OnboardingScreen
        user={user}
        onComplete={async () => {
          await loadUser();
        }}
      />
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
        {/* Use CSS display instead of conditional rendering to preserve DOM state (scroll position) */}
        <div style={{ display: activeTab === 'home' ? 'block' : 'none' }}>
          <HomeTab user={user} onRefresh={loadUser} />
        </div>
        <div style={{ display: activeTab === 'engage' ? 'block' : 'none' }}>
          <EngageTab user={user} onUserUpdate={loadUser} engageData={engageData} setEngageData={setEngageData} settings={settings} activeTab={activeTab} />
        </div>
        <div style={{ display: activeTab === 'campaigns' ? 'block' : 'none' }}>
          <CampaignsTab user={user} />
        </div>
        <div style={{ display: activeTab === 'earn' ? 'block' : 'none' }}>
          <EarnTab />
        </div>
        <div style={{ display: activeTab === 'loud' ? 'block' : 'none' }}>
          <LoudTab user={user} />
        </div>
      </div>

      {/* Coming Soon Toast - Simple fade up */}
      {comingSoonToast && (
        <div
          className={`fixed bottom-28 left-0 right-0 flex justify-center z-50 pointer-events-none transition-all duration-400 ease-out ${
            toastVisible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-6'
          }`}
        >
          <div className="px-4 py-2.5 rounded-full text-sm text-white/80 text-center whitespace-pre-line bg-black/70 backdrop-blur-sm">
            {comingSoonToast}
          </div>
        </div>
      )}

      {/* Bottom Tab Bar - Floating Glassmorphism Pill with Magic UI */}
      <div className="fixed bottom-0 left-0 right-0 flex justify-center px-6 tg-safe-area-bottom pointer-events-none">
        <div
          className="relative rounded-3xl p-2 pointer-events-auto"
          style={{
            background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.1) 0%, rgba(15, 10, 11, 0.92) 50%, rgba(249, 84, 0, 0.08) 100%)',
            backdropFilter: 'blur(40px) saturate(180%)',
            WebkitBackdropFilter: 'blur(40px) saturate(180%)',
            border: '1px solid rgba(249, 84, 0, 0.3)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8), 0 0 40px rgba(249, 84, 0, 0.08), 0 1px 0 rgba(249, 84, 0, 0.15) inset'
          }}
        >
          <div className="flex items-center gap-1">
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
              icon={<TargetIconFill className="w-6 h-6" />}
              iconOutline={<TargetIcon className="w-6 h-6" />}
              label="Campaigns"
              active={activeTab === 'campaigns'}
              onClick={() => handleTabChange('campaigns')}
            />
            <TabButton
              tabId="earn"
              icon={<StarIconFill />}
              iconOutline={<StarIcon />}
              label="Earn"
              active={false}
              onClick={() => {
                hapticFeedback('light');
                showComingSoonToast('Earn is coming soon.\nKarma will play main role here.');
              }}
            />
            <TabButton
              tabId="loud"
              icon={<FireIconFill />}
              iconOutline={<FireIcon />}
              label="Loud"
              active={!!(user?.loud_access && activeTab === 'loud')}
              onClick={() => {
                if (user?.loud_access) {
                  handleTabChange('loud');
                } else {
                  hapticFeedback('light');
                  showComingSoonToast('LOUD Campaigns will be launching soon!');
                }
              }}
            />
          </div>
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
      className={`relative z-10 flex flex-col items-center justify-center flex-1 px-3 py-2 rounded-2xl transition-all active:scale-95 ${
        active ? 'text-[#f95400]' : 'text-gray-500 hover:text-gray-400'
      }`}
    >
      <div
        className="w-6 h-6 flex items-center justify-center mb-1 transition-all"
        style={{
          filter: active ? 'drop-shadow(0 0 8px rgba(249, 84, 0, 0.6))' : 'none',
        }}
      >
        <div className="w-5 h-5">{active ? icon : iconOutline}</div>
      </div>
      <span className={`text-[9px] font-semibold text-center w-full ${active ? 'text-[#f95400]' : ''}`}>
        {label}
      </span>
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
    <div className="fixed top-0 left-0 right-0 bg-black/90 backdrop-blur-xl border-b border-[#f95400]/20 z-40 tg-safe-area-top">
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
            className="glass-pill flex items-center gap-2 hover:bg-white/10 transition-all"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#f95400] to-[#ff7020] flex items-center justify-center">
              <span className="text-xs font-bold text-black">
                {telegramUsername.charAt(0).toUpperCase()}
              </span>
            </div>
            <span className="text-sm text-gray-300 max-w-[100px] truncate">
              {telegramUsername}
            </span>
            <ChevronDownIconFill className={`w-4 h-4 text-gray-400 transition-transform ${showProfileMenu ? 'rotate-180' : ''}`} />
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
              <div className="absolute right-0 top-full mt-2 w-64 z-50 overflow-hidden slide-up rounded-2xl" style={{
                background: '#0A0A0A',
                border: '1px solid rgba(249, 84, 0, 0.25)',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.9), 0 1px 0 rgba(249, 84, 0, 0.1) inset'
              }}>
                {/* Telegram Account */}
                <div className="px-4 py-3 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="glass-icon glass-icon-md">
                      <TelegramIcon className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-400">Telegram</p>
                      <p className="text-sm font-medium text-white truncate">@{telegramUsername}</p>
                    </div>
                  </div>
                </div>

                {/* X Account - clickable if not connected */}
                {xUsername ? (
                  <div className="px-4 py-3 border-b border-white/[0.06]">
                    <div className="flex items-center gap-3">
                      <div className="glass-icon glass-icon-md">
                        <XLogoIcon className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
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
                    className="w-full px-4 py-3 border-b border-white/[0.06] flex items-center gap-3 hover:bg-white/[0.04] transition-colors"
                  >
                    <div className="glass-icon glass-icon-md">
                      <XLogoIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0 text-left">
                      <p className="text-xs text-gray-400">X Account</p>
                      <p className="text-sm text-[#f95400]">Link your account</p>
                    </div>
                    <ChevronRightIconFill className="w-4 h-4 text-gray-500" />
                  </button>
                )}

                {/* Discord */}
                <div className="px-4 py-3 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="glass-icon glass-icon-md">
                      <DiscordIcon className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
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
                  className="w-full px-4 py-3 flex items-center gap-3 hover:bg-white/[0.04] transition-colors"
                >
                  <div className="glass-icon glass-icon-md">
                    <ChartIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
                  </div>
                  <div className="flex-1 text-left">
                    <p className="text-sm font-medium text-white">Stats</p>
                    <p className="text-xs text-gray-400">View your performance</p>
                  </div>
                  <ChevronRightIconFill className="w-4 h-4 text-gray-500" />
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
  const [showTierInfo, setShowTierInfo] = useState(false);

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

  // Tier data for the info modal
  const tierData = [
    { name: 'GOAT', minPoints: 1000, multiplier: '1.35x' },
    { name: 'OG', minPoints: 800, multiplier: '1.30x' },
    { name: 'Legend', minPoints: 600, multiplier: '1.25x' },
    { name: 'Based', minPoints: 400, multiplier: '1.20x' },
    { name: 'Degen', minPoints: 200, multiplier: '1.15x' },
    { name: 'Normie', minPoints: 100, multiplier: '1.10x' },
    { name: 'Anon', minPoints: 0, multiplier: '1.0x' },
  ];

  return (
    <div className="p-4 space-y-4">
      {/* Balance Card - High-Tech Design */}
      <div className="relative overflow-hidden rounded-2xl border border-[#f95400]/20 bg-gradient-to-br from-black via-zinc-900/50 to-black">
        {/* Grid Pattern Background */}
        <div className="absolute inset-0 opacity-[0.07]" style={{
          backgroundImage: `linear-gradient(#f95400 1px, transparent 1px), linear-gradient(90deg, #f95400 1px, transparent 1px)`,
          backgroundSize: '24px 24px'
        }} />

        {/* Scan line effect */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#f95400]/[0.03] to-transparent" />

        <div className="relative z-10 p-6">
          {/* Header Row */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="glass-icon glass-icon-md glass-icon-orange">
                <WalletIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
              </div>
              <div>
                <p className="text-sm text-[#f95400] uppercase tracking-wider">Balance</p>
                <p className="text-xs text-white">{scoreMultiplier} multiplier</p>
              </div>
            </div>
            <button
              onClick={() => setShowTierInfo(true)}
              className="px-4 py-2 rounded-full flex items-center gap-2 transition-all active:scale-95 cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(249, 84, 0, 0.4)',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4), 0 1px 0 rgba(255, 140, 66, 0.2) inset'
              }}
            >
              <span className="text-xs font-bold uppercase tracking-wide text-white">{scoreTier}</span>
            </button>
          </div>

          {/* Main Balance Display */}
          <div className="mb-6">
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-bold tracking-tight gold-gradient-text">{formatKarma(user.credits)}</span>
              <div className="flex items-center gap-1 mb-0.5">
                <BoltIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
                <span className="text-lg text-white font-light">karma</span>
              </div>
            </div>
          </div>

          {/* Engagement Progress - Magic UI card with BorderBeam */}
          <div className="relative rounded-2xl overflow-hidden p-4" style={{
            background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
            backdropFilter: 'blur(32px) saturate(160%)',
            WebkitBackdropFilter: 'blur(32px) saturate(160%)',
            border: '1px solid rgba(249, 84, 0, 0.15)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset'
          }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="glass-icon glass-icon-sm glass-icon-orange">
                  <TrendingUpIconFill className="w-3.5 h-3.5" style={ICON_GRADIENT_STYLE} />
                </div>
                <span className="text-sm font-semibold text-white">Today's Progress</span>
              </div>
              <span className="text-sm font-mono font-bold text-white">
                {user.engaged_today || 0}
                <span className="text-gray-400">/{(user.engaged_today || 0) + (user.available_posts || 0)}</span>
              </span>
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden ring-1 ring-white/20">
              <div
                className="h-full rounded-full transition-all duration-500 relative overflow-hidden"
                style={{
                  background: 'linear-gradient(90deg, #f95400 0%, #ff8c42 50%, #f95400 100%)',
                  backgroundSize: '200% 100%',
                  animation: 'progress-shine 3s ease-in-out infinite',
                  boxShadow: '0 0 12px rgba(249, 84, 0, 0.3), 0 1px 0 rgba(255, 140, 66, 0.4) inset',
                  width: `${((user.engaged_today || 0) + (user.available_posts || 0)) > 0
                    ? ((user.engaged_today || 0) / ((user.engaged_today || 0) + (user.available_posts || 0))) * 100
                    : 0}%`
                }}
              />
            </div>
            {(user.available_posts || 0) > 0 ? (
              <p className="text-xs text-gray-300 font-medium mt-2">{user.available_posts} posts waiting for you</p>
            ) : (
              <p className="text-xs text-[#f95400] mt-2">All caught up! Submit a post to earn more</p>
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
          className="group relative overflow-hidden rounded-xl p-4 text-left transition-all active:scale-[0.98]"
          style={{
            background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.12) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.08) 100%)',
            backdropFilter: 'blur(32px) saturate(160%)',
            WebkitBackdropFilter: 'blur(32px) saturate(160%)',
            border: '1px solid rgba(249, 84, 0, 0.4)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.15) inset'
          }}
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f95400]/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
          <div className="glass-icon glass-icon-md glass-icon-orange mb-2">
            <BoltIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
          </div>
          <p className="text-sm font-bold text-white">Start Engaging</p>
          <p className="text-xs text-gray-300">Earn karma now</p>
        </button>
        <button
          onClick={() => {
            hapticFeedback('light');
            const campaignsTab = document.querySelector('[data-tab="campaigns"]') as HTMLButtonElement;
            if (campaignsTab) campaignsTab.click();
          }}
          className="group relative overflow-hidden rounded-xl bg-white/[0.03] border border-white/[0.08] p-4 text-left transition-all hover:border-[#f95400]/30 active:scale-[0.98]"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f95400]/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
          <div className="glass-icon glass-icon-md glass-icon-orange mb-2">
            <TargetIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
          </div>
          <p className="text-sm font-semibold text-white">Campaigns</p>
          <p className="text-xs text-gray-500">Coming soon</p>
        </button>
      </div>

      {/* Streak Card */}
      <StreakCard currentStreak={user.current_streak} />

      {/* Tier Info Modal */}
      {showTierInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setShowTierInfo(false)}
          />

          {/* Modal */}
          <div
            className="relative w-full max-w-sm rounded-2xl p-5 animate-slide-up"
            style={{
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
              backdropFilter: 'blur(32px) saturate(160%)',
              WebkitBackdropFilter: 'blur(32px) saturate(160%)',
              border: '1px solid rgba(249, 84, 0, 0.15)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center"
                  style={{
                    background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(249, 84, 0, 0.08) 100%)',
                    border: '1px solid rgba(249, 84, 0, 0.3)',
                  }}
                >
                  <TrophyIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
                </div>
                <h3 className="text-base font-semibold text-white">Creator Tiers</h3>
              </div>
              <button
                onClick={() => setShowTierInfo(false)}
                className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:bg-white/10"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
              >
                <XIconFill className="w-4 h-4 text-gray-400" />
              </button>
            </div>

            {/* Tiers List */}
            <div className="space-y-2 mb-5">
              {tierData.map((tier) => {
                const isCurrentTier = tier.name === scoreTier;
                const isAchieved = tweetscoutScore >= tier.minPoints;

                return (
                  <div
                    key={tier.name}
                    className="flex items-center justify-between py-2.5 px-3 rounded-xl transition-all"
                    style={{
                      background: isCurrentTier
                        ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.15) 0%, rgba(249, 84, 0, 0.05) 100%)'
                        : 'transparent',
                      border: isCurrentTier
                        ? '1px solid rgba(249, 84, 0, 0.4)'
                        : '1px solid rgba(255, 255, 255, 0.06)',
                      opacity: !isAchieved && !isCurrentTier ? 0.4 : 1,
                    }}
                  >
                    <span className={`text-sm font-medium ${isCurrentTier ? 'text-[#f95400]' : 'text-white'}`}>
                      {tier.name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-gray-500">
                        {tier.minPoints}+ pts
                      </span>
                      <span
                        className="text-xs font-mono font-semibold px-2 py-0.5 rounded-md"
                        style={{
                          background: isCurrentTier ? 'rgba(249, 84, 0, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                          color: isCurrentTier ? '#f95400' : '#9ca3af',
                        }}
                      >
                        {tier.multiplier}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Note */}
            <p className="text-xs text-gray-500 text-center">
              Your TweetScout score is <span className="text-[#f95400]">{Math.round(tweetscoutScore)}</span> and determines your multiplier
            </p>
          </div>
        </div>
      )}
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
    <div className="relative overflow-hidden rounded-xl p-4" style={{
      background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.03) 0%, rgba(15, 10, 11, 0.6) 50%, rgba(249, 84, 0, 0.02) 100%)',
      backdropFilter: 'blur(40px) saturate(180%)',
      WebkitBackdropFilter: 'blur(40px) saturate(180%)',
      border: '1px solid rgba(249, 84, 0, 0.2)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8), 0 1px 0 rgba(249, 84, 0, 0.08) inset'
    }}>
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
        <div className={`glass-icon glass-icon-md ${currentStreak > 0 ? 'glass-icon-orange' : ''}`}>
          <FireIconFill className="w-5 h-5" style={currentStreak > 0 ? ICON_GRADIENT_STYLE : { color: 'white' }} />
        </div>
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className={`text-2xl font-bold ${currentStreak > 0 ? 'text-white' : 'text-gray-500'}`}>
              {currentStreak}
            </span>
            <span className="text-sm font-bold text-gray-300">day streak</span>
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
              <div className={`w-full h-9 rounded-lg flex items-center justify-center transition-all ${
                isCompleted
                  ? 'bg-gradient-to-b from-[#f95400] to-[#ff8c42] shadow-lg shadow-orange-500/30 ring-2 ring-orange-500/20'
                  : isToday
                  ? 'bg-orange-500/15 border-2 border-orange-500/50 border-dashed'
                  : isFuture
                  ? 'bg-white/5 border border-white/10'
                  : 'bg-white/10 border border-white/20'
              }`}>
                {isCompleted && <CheckIconFill className="w-4 h-4 drop-shadow-lg" style={ICON_GRADIENT_STYLE} />}
              </div>
              <span className={`text-[10px] font-bold ${
                isCompleted ? 'text-orange-400' : isToday ? 'text-orange-300' : 'text-gray-400'
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

// CAMPAIGNS TAB (Interest Registration)
function CampaignsTab({ user }: { user: User | null }) {
  const [showInterestModal, setShowInterestModal] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);

  // Check if user already registered interest
  useEffect(() => {
    const checkRegistration = async () => {
      if (!user) {
        setCheckingStatus(false);
        return;
      }
      try {
        const response = await api.getFeatureInterest('campaigns');
        setRegistered(response.registered);
      } catch {
        // Ignore errors
      } finally {
        setCheckingStatus(false);
      }
    };
    checkRegistration();
  }, [user]);

  const glassCardStyle = {
    background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
    backdropFilter: 'blur(32px) saturate(160%)',
    WebkitBackdropFilter: 'blur(32px) saturate(160%)',
    border: '1px solid rgba(249, 84, 0, 0.15)',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset'
  };

  return (
    <div className="flex items-center justify-center min-h-[70vh] p-4">
      {/* Popup Card */}
      <div
        className="w-full max-w-sm rounded-2xl p-5"
        style={{
          background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
          backdropFilter: 'blur(32px) saturate(160%)',
          WebkitBackdropFilter: 'blur(32px) saturate(160%)',
          border: '1px solid rgba(249, 84, 0, 0.15)',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset',
        }}
      >
        {/* Header */}
        <div className="flex flex-col items-center mb-5">
          <div className="glass-icon glass-icon-lg glass-icon-orange mb-4">
            <TargetIconFill className="w-6 h-6" style={ICON_GRADIENT_STYLE} />
          </div>
          <h3 className="text-base font-semibold text-white mb-1">Campaigns</h3>
          <span
            className="text-xs font-mono font-semibold px-3 py-1 rounded-full"
            style={{ background: 'rgba(249, 84, 0, 0.2)', color: '#f95400' }}
          >
            Coming Soon
          </span>
        </div>

        {/* Description */}
        <p className="text-xs text-gray-500 text-center mb-5">
          Exclusive reward campaigns from top projects. Register your interest to get notified when we launch.
        </p>

        {/* CTA */}
        {checkingStatus ? (
          <div className="flex justify-center py-3">
            <div className="w-6 h-6 border-2 border-[#f95400]/30 border-t-[#f95400] rounded-full animate-spin" />
          </div>
        ) : registered ? (
          <div
            className="h-12 rounded-2xl flex items-center justify-center gap-2"
            style={{
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
              border: '1px solid rgba(249, 84, 0, 0.4)',
            }}
          >
            <CheckIconFill className="w-5 h-5 text-white" />
            <span className="text-white font-semibold text-sm">You&apos;re on the list!</span>
          </div>
        ) : (
          <button
            onClick={() => {
              hapticFeedback('medium');
              setShowInterestModal(true);
            }}
            className="w-full h-12 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-95"
            style={{
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(249, 84, 0, 0.4)',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
              color: 'white',
            }}
          >
            Register Interest
          </button>
        )}
      </div>

      {/* Interest Modal */}
      <CampaignInterestModal
        isOpen={showInterestModal}
        onClose={() => setShowInterestModal(false)}
        onSuccess={() => {
          setRegistered(true);
          setShowInterestModal(false);
          hapticFeedback('success');
        }}
      />
    </div>
  );
}

// Campaign Interest Modal
function CampaignInterestModal({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const options = [
    { id: 'airdrops', label: 'Airdrops' },
    { id: 'token_rewards', label: 'Token Rewards' },
    { id: 'nfts', label: 'NFTs' },
    { id: 'exclusive_access', label: 'Exclusive Access' },
  ];

  const toggleOption = (id: string) => {
    hapticFeedback('light');
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.registerFeatureInterest('campaigns', selected);
      onSuccess();
    } catch {
      hapticFeedback('error');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div
        className="relative w-full max-w-sm rounded-2xl p-5 animate-slide-up"
        style={{
          background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
          backdropFilter: 'blur(32px) saturate(160%)',
          WebkitBackdropFilter: 'blur(32px) saturate(160%)',
          border: '1px solid rgba(249, 84, 0, 0.15)',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="glass-icon glass-icon-sm glass-icon-orange">
              <TargetIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
            </div>
            <h3 className="text-base font-semibold text-white">What interests you?</h3>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:bg-white/10"
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <XIconFill className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Options */}
        <div className="space-y-2 mb-5">
          {options.map(option => (
            <button
              key={option.id}
              onClick={() => toggleOption(option.id)}
              className="w-full py-2.5 px-3 rounded-xl text-left transition-all flex items-center justify-between"
              style={{
                background: selected.includes(option.id)
                  ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.15) 0%, rgba(249, 84, 0, 0.05) 100%)'
                  : 'transparent',
                border: selected.includes(option.id)
                  ? '1px solid rgba(249, 84, 0, 0.4)'
                  : '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              <span className={`text-sm font-medium ${selected.includes(option.id) ? 'text-[#f95400]' : 'text-white'}`}>
                {option.label}
              </span>
              {selected.includes(option.id) && (
                <CheckIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
              )}
            </button>
          ))}
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={selected.length === 0 || submitting}
          className="w-full h-12 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-50"
          style={{
            background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid rgba(249, 84, 0, 0.4)',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
            color: 'white',
          }}
        >
          {submitting ? (
            <>
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Submitting...
            </>
          ) : (
            'Submit'
          )}
        </button>
      </div>
    </div>
  );
}

// EARN TAB (Coming Soon)
function EarnTab() {
  return (
    <div className="p-4 flex flex-col items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-sm">
        <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-[#f95400]/20 to-[#CC5500]/20 border border-[#f95400]/30 flex items-center justify-center">
          <StarIconFill className="w-12 h-12 text-[#f95400]/60" />
        </div>
        <h2 className="text-2xl font-bold mb-2 gold-gradient-text">Earn Rewards</h2>
        <p className="text-gray-400 mb-4">
          Participate in giveaways and burn karma for rewards.
        </p>
        <div className="px-4 py-2 rounded-full bg-[#f95400]/10 border border-[#f95400]/20">
          <span className="text-sm text-[#f95400] font-medium">Coming Soon</span>
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
  activeTab,
}: {
  user: User | null;
  onUserUpdate: () => void;
  engageData: EngageData;
  setEngageData: React.Dispatch<React.SetStateAction<EngageData>>;
  settings: AppSettings | null;
  activeTab: string;
}) {
  // Extract state from lifted engageData
  const { state, session, currentPostIndex, engagedPosts, error, result, lastFetchedAt, claimHistory, hasProcessingBatch, isClaimLoading } = engageData;

  // Helper to update specific fields
  const updateEngageData = (updates: Partial<EngageData>) => {
    setEngageData(prev => ({ ...prev, ...updates }));
  };

  // Local state (not persisted across tab switches)
  const [clickedPost, setClickedPost] = useState<string | null>(null);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [likeIntentEnabled, setLikeIntentEnabled] = useState(true); // Default ON
  const [refreshing, setRefreshing] = useState(false);
  const [showClaimTooltip, setShowClaimTooltip] = useState(false);
  const [showFailurePopup, setShowFailurePopup] = useState(false);
  const [failedCount, setFailedCount] = useState(0);
  const [earnedKarma, setEarnedKarma] = useState(0); // Karma earned in the batch (shown in popup)
  const [showEngageInfo, setShowEngageInfo] = useState(false);

  // Refs
  const carouselRef = useRef<HTMLDivElement>(null);
  const clickedPostRef = useRef<string | null>(null);
  const sessionRef = useRef<SessionResponse | null>(null);
  const engagedPostsRef = useRef<Set<string>>(new Set());
  const currentPostIndexRef = useRef(0);
  const isScrollingRef = useRef(false); // Flag to disable onScroll during programmatic scroll
  const claimTooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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
      // Only run when Engage tab is active to prevent scroll reset during tab switches
      if (document.visibilityState === 'visible' && activeTab === 'engage') {
        handleReturn();
      }
    };

    // Also listen for focus - handles desktop browser tab switching
    const handleFocus = () => {
      // Only run when Engage tab is active
      if (activeTab === 'engage') {
        handleReturn();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [state, setEngageData, activeTab]);

  // Reset isScrollingRef on unmount to prevent stuck state
  useEffect(() => {
    return () => {
      isScrollingRef.current = false;
    };
  }, []);

  // Auto-load posts when entering Engage tab (skip idle screen)
  useEffect(() => {
    if (activeTab === 'engage' && state === 'idle' && user) {
      startSession();
    }
  }, [activeTab, state, user]);

  // NOTE: Scroll lock no longer needed - we only render cards up to maxAllowed + 1
  // so there's nothing to scroll to beyond unlocked cards

  const startSession = async (skipPendingRestore = false) => {
    try {
      updateEngageData({ state: 'loading', error: null, result: null });

      const data = await api.startSession();

      // Check if user has 10+ pending engagements - show verification immediately
      // Skip this check if we're doing a fresh start after claim
      if (data.show_verification && !skipPendingRestore) {
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
        // Use pending_post_ids to restore progress, OR empty set for fresh start after claim
        const pendingSet = skipPendingRestore ? new Set<string>() : new Set(data.pending_post_ids || []);
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
        console.log('[Session] Started, firstUnengagedIndex:', firstUnengagedIndex, 'totalPosts:', data.posts.length, 'engagedCount:', pendingSet.size);
        if (firstUnengagedIndex > 0) {
          requestAnimationFrame(() => {
            const container = carouselRef.current;
            if (container) {
              isScrollingRef.current = true;
              const cardWidth = container.offsetWidth * 0.8;
              const spacerWidth = container.offsetWidth * 0.1;
              const targetScroll = spacerWidth + (firstUnengagedIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
              console.log('[Session] Initial scroll to index:', firstUnengagedIndex, 'targetScroll:', Math.round(targetScroll));
              container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'instant' });
              setTimeout(() => { isScrollingRef.current = false; }, 100);
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

    // IMMEDIATE: Open link first - hyperlink speed, no delay
    openLink(getEngageUrl(post));
    hapticFeedback('light'); // After link opens

    // Fire API call in background (don't wait)
    api.recordClick(post.id).catch(err => {
      console.error('[Engage] Failed to record click:', err);
    });

    // Small delay before updating UI (badge, scroll) - let redirect happen first
    setTimeout(() => {
      // Mark as engaged
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

      console.log('[Engage] Post clicked, finding next unengaged. Current:', currentPostIndex, 'Next:', nextIndex, 'Total:', posts.length);

      // Update refs
      currentPostIndexRef.current = nextIndex;

      // Direct DOM scroll - no React state dependency
      const container = carouselRef.current;
      if (container) {
        isScrollingRef.current = true; // Prevent onScroll interference
        const cardWidth = container.offsetWidth * 0.8;
        const spacerWidth = container.offsetWidth * 0.1;
        const targetScroll = spacerWidth + (nextIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
        console.log('[Engage] Scrolling to index:', nextIndex, 'targetScroll:', Math.round(targetScroll));
        container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'smooth' });
        setTimeout(() => { isScrollingRef.current = false; }, 350);
      }

      // Update React state for UI (checkmarks, counter)
      setEngageData(prev => ({
        ...prev,
        engagedPosts: newEngaged,
        currentPostIndex: nextIndex,
      }));

      hapticFeedback('success');
    }, 100); // 100ms delay - enough for redirect to start
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

  // Fetch claim history (for polling and initial load)
  const fetchClaimHistory = async () => {
    try {
      const data = await api.getClaimHistory();
      updateEngageData({
        claimHistory: data.batches,
        hasProcessingBatch: data.has_processing,
      });
      return data;
    } catch (err) {
      console.error('Failed to fetch claim history:', err);
      return null;
    }
  };

  // Poll for claim history updates when there's a processing batch
  useEffect(() => {
    if (!hasProcessingBatch) return;

    const interval = setInterval(async () => {
      const data = await fetchClaimHistory();
      if (data && !data.has_processing) {
        // Processing complete - check results
        const recentBatch = data.batches?.[0];
        const failedNum = recentBatch?.failed ?? 0;
        const creditsEarned = recentBatch?.credits_awarded ?? 0;

        // Always show popup with results (earned + failed)
        setFailedCount(failedNum);
        setEarnedKarma(creditsEarned);
        setShowFailurePopup(true);
        hapticFeedback(failedNum > 0 ? 'error' : 'success');

        // Refresh user data (balance updated)
        onUserUpdate();
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [hasProcessingBatch]);

  const completeSession = async () => {
    // Queue-based verification (like spot trading)

    // Prevent double-click
    if (isClaimLoading) return;

    updateEngageData({ isClaimLoading: true });

    try {
      hapticFeedback('medium');

      const data = await api.queueClaim();

      if (!data.success) {
        // Show error (e.g., not enough engagements, time limit)
        updateEngageData({
          state: 'error',
          error: data.message,
          isClaimLoading: false,
        });
        hapticFeedback('error');
        return;
      }

      // Success - verification queued!
      hapticFeedback('success');

      // Immediately clear engaged posts for instant visual feedback
      engagedPostsRef.current = new Set<string>();
      currentPostIndexRef.current = 0;
      updateEngageData({
        engagedPosts: new Set<string>(),
        currentPostIndex: 0,
        hasProcessingBatch: true, // Show "Processing..." immediately
      });

      // Scroll carousel to first card instantly
      if (carouselRef.current) {
        carouselRef.current.scrollTo({ left: 0, behavior: 'instant' });
      }

      // Fetch updated claim history and fresh cards in parallel (background)
      const [historyData, sessionData] = await Promise.all([
        fetchClaimHistory(),
        api.startSession(),
      ]);

      // Update with fresh cards - smooth swap
      updateEngageData({
        state: 'ready',
        session: sessionData,
        claimHistory: historyData?.batches || [],
        hasProcessingBatch: historyData?.has_processing || true,
        isClaimLoading: false,
        lastFetchedAt: Date.now(),
      });

    } catch (err) {
      updateEngageData({
        state: 'error',
        error: err instanceof Error ? err.message : 'Failed to queue verification',
        isClaimLoading: false,
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
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
        <div
          className="relative w-full max-w-sm rounded-2xl p-5 animate-slide-up text-center"
          style={{
            background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
            backdropFilter: 'blur(32px) saturate(160%)',
            WebkitBackdropFilter: 'blur(32px) saturate(160%)',
            border: '1px solid rgba(249, 84, 0, 0.15)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset',
          }}
        >
          {/* Icon */}
          <div className="flex justify-center mb-4">
            <div className="glass-icon glass-icon-md glass-icon-orange">
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="url(#iconGradient)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <defs>
                  <linearGradient id="iconGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#f95400" />
                    <stop offset="100%" stopColor="#ff8c42" />
                  </linearGradient>
                </defs>
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
          </div>

          {/* Title */}
          <h3 className="text-lg font-semibold mb-2">Posts Outdated</h3>

          {/* Description */}
          <p className="text-gray-400 mb-5 text-sm">
            Your posts are more than 20 minutes old. Refresh to see the latest available posts.
          </p>

          {/* CTA Button */}
          <button
            onClick={handleMandatoryRefresh}
            disabled={refreshing}
            className="w-full h-12 rounded-xl font-medium text-sm transition-all duration-200 flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(249, 84, 0, 0.4)',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
              color: 'white',
            }}
          >
            {refreshing ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Refreshing...
              </span>
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
        <div className="fixed inset-0 flex flex-col items-center justify-center overflow-hidden bg-black p-4">
          <div className="text-center max-w-sm">
            <div className="w-24 h-24 mx-auto mb-6 rounded-full gold-gradient-bg flex items-center justify-center glow-gold pulse-gold">
              <BoltIconFill className="w-12 h-12 text-black" />
            </div>
            <h2 className="text-2xl font-bold mb-2 gold-gradient-text">Ready to Engage?</h2>
            <p className="text-gray-400 mb-8">
              Engage with posts to earn karma. Each engagement takes about 30 seconds.
            </p>
            <button onClick={() => startSession()} className="btn-primary w-full text-lg py-4">
              Start Engaging
            </button>
            <button
              onClick={() => {
                hapticFeedback('light');
                setShowSubmitModal(true);
              }}
              className="btn-secondary w-full mt-3 flex items-center justify-center gap-2"
            >
              <PlusIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
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
      <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-black">
        <PixelLoader />
      </div>
    );
  }

  // Error state
  if (state === 'error') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />

        {/* Modal */}
        <div
          className="relative w-full max-w-sm rounded-2xl p-5 animate-slide-up"
          style={{
            background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
            backdropFilter: 'blur(32px) saturate(160%)',
            WebkitBackdropFilter: 'blur(32px) saturate(160%)',
            border: '1px solid rgba(249, 84, 0, 0.15)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset',
          }}
        >
          {/* Header */}
          <div className="flex flex-col items-center mb-5">
            <div className="glass-icon glass-icon-md glass-icon-orange mb-4">
              <XIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
            </div>
            <h3 className="text-base font-semibold text-white">Something went wrong</h3>
          </div>

          {/* Error message */}
          <p className="text-xs text-gray-500 text-center mb-5">{error}</p>

          {/* Button */}
          <button
            onClick={() => startSession()}
            className="w-full h-12 rounded-2xl text-sm font-semibold flex items-center justify-center transition-all active:scale-95"
            style={{
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(249, 84, 0, 0.4)',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
              color: 'white',
            }}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Engaging state - user is on X, will auto-advance when they return
  if (state === 'engaging') {
    return (
      <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-black p-4">
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
      <div className="fixed inset-0 flex flex-col items-center justify-center overflow-hidden bg-black">
        <PixelLoader />
        <p className="text-gray-400 mt-4">Verifying your engagements...</p>
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
        <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-black p-4">
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
                <button onClick={() => startSession()} className="btn-primary w-full">
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
                <button onClick={() => startSession()} className="btn-primary w-full">
                  Engage More
                </button>
              </>
            ) : (
              // No credits / other - could be failed verifications or no posts
              <>
                <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-black/50 border border-[#f95400]/30 flex items-center justify-center">
                  <InfoIconFill className="w-12 h-12 text-[#f95400]" />
                </div>
                <h2 className="text-xl font-bold mb-2">{result?.message || 'Session Complete'}</h2>
                <p className="text-gray-400 mb-8">Tap below to re-engage and earn karma</p>
                <button onClick={() => startSession()} className="btn-primary w-full">
                  Start Engaging
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
                <PlusIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
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
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-white leading-none">Engage</h2>
              <button
                onClick={() => {
                  hapticFeedback('light');
                  setShowEngageInfo(true);
                }}
                className="w-5 h-5 rounded-full bg-white/[0.05] flex items-center justify-center hover:bg-white/[0.1] transition-colors -mt-0.5"
              >
                <span className="text-[10px] text-gray-500 font-medium leading-none">i</span>
              </button>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="flex items-center gap-1.5 px-3 py-1 rounded-full text-sm"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: 'rgba(255, 255, 255, 0.6)',
                }}
              >
                <span className="font-semibold">{(session?.posts?.length || 0) - engagedPosts.size}</span>
                <span className="text-xs opacity-70">available</span>
              </div>
              <div
                className="flex items-center gap-1.5 px-3 py-1 rounded-full text-sm"
                style={{
                  background: engagedPosts.size > 0
                    ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.25) 0%, rgba(249, 84, 0, 0.15) 100%)'
                    : 'rgba(255, 255, 255, 0.05)',
                  border: engagedPosts.size > 0 ? '1px solid rgba(249, 84, 0, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
                  color: engagedPosts.size > 0 ? '#ff8c42' : 'rgba(255, 255, 255, 0.6)',
                }}
              >
                <span className="font-semibold">{engagedPosts.size}</span>
                <span className="text-xs opacity-70">queue</span>
              </div>
            </div>
          </div>
          <div className="h-2.5 bg-white/10 rounded-full overflow-hidden ring-1 ring-white/20">
            <div
              className="h-full rounded-full transition-all duration-500 relative overflow-hidden"
              style={{
                background: 'linear-gradient(90deg, #f95400 0%, #ff8c42 50%, #f95400 100%)',
                backgroundSize: '200% 100%',
                animation: 'progress-shine 3s ease-in-out infinite',
                boxShadow: '0 0 12px rgba(249, 84, 0, 0.3), 0 1px 0 rgba(255, 140, 66, 0.4) inset',
                width: `${progress}%`
              }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">Post {currentPostIndex + 1} of {session?.posts?.length || 0}</p>

          {/* Like Intent Toggle */}
          <div
            className="flex items-center justify-between mt-3 p-3 rounded-xl transition-all"
            style={{
              background: likeIntentEnabled
                ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.08) 0%, rgba(15, 10, 11, 0.6) 100%)'
                : 'linear-gradient(135deg, rgba(255, 255, 255, 0.03) 0%, rgba(15, 10, 11, 0.6) 100%)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: likeIntentEnabled ? '1px solid rgba(249, 84, 0, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: likeIntentEnabled ? '0 0 20px rgba(249, 84, 0, 0.1)' : 'none'
            }}
          >
            <div className="flex items-center gap-2">
              <div className="glass-icon glass-icon-sm glass-icon-orange">
                <HeartIconFill className="w-3.5 h-3.5" style={ICON_GRADIENT_STYLE} />
              </div>
              <span className="text-sm font-medium text-white">Quick Like</span>
            </div>
            <button
              onClick={() => {
                hapticFeedback('light');
                setLikeIntentEnabled(!likeIntentEnabled);
              }}
              className={`relative w-11 h-6 rounded-full transition-all duration-200 ${
                likeIntentEnabled ? 'bg-[#f95400] shadow-[0_0_12px_rgba(249,84,0,0.4)]' : 'bg-white/20'
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
        <div className="overflow-hidden">
          {/* Cards with nav buttons wrapper */}
          <div className="relative">
          {/* Left navigation button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (currentPostIndex > 0) {
                const newIndex = currentPostIndex - 1;
                updateEngageData({ currentPostIndex: newIndex });
                const container = carouselRef.current;
                if (container) {
                  isScrollingRef.current = true;
                  const cardWidth = container.offsetWidth * 0.8;
                  const spacerWidth = container.offsetWidth * 0.1;
                  const targetScroll = spacerWidth + (newIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
                  container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'smooth' });
                  setTimeout(() => { isScrollingRef.current = false; }, 350);
                }
              }
            }}
            disabled={currentPostIndex <= 0}
            className="absolute left-2 top-[140px] -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-95"
            style={{
              background: currentPostIndex > 0
                ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.15) 0%, rgba(0, 0, 0, 0.6) 100%)'
                : 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: currentPostIndex > 0 ? '1px solid rgba(249, 84, 0, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
              color: currentPostIndex > 0 ? '#fff' : 'rgba(255, 255, 255, 0.3)',
              cursor: currentPostIndex <= 0 ? 'not-allowed' : 'pointer',
              boxShadow: currentPostIndex > 0 ? '0 4px 12px rgba(0, 0, 0, 0.4)' : 'none'
            }}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          {/* Right navigation button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              const maxAllowed = currentPostIndexRef.current;
              if (currentPostIndex < maxAllowed) {
                const newIndex = currentPostIndex + 1;
                updateEngageData({ currentPostIndex: newIndex });
                const container = carouselRef.current;
                if (container) {
                  isScrollingRef.current = true;
                  const cardWidth = container.offsetWidth * 0.8;
                  const spacerWidth = container.offsetWidth * 0.1;
                  const targetScroll = spacerWidth + (newIndex * (cardWidth + 12)) - (container.offsetWidth - cardWidth) / 2;
                  container.scrollTo({ left: Math.max(0, targetScroll), behavior: 'smooth' });
                  setTimeout(() => { isScrollingRef.current = false; }, 350);
                }
              }
            }}
            disabled={currentPostIndex >= currentPostIndexRef.current}
            className="absolute right-2 top-[140px] -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-95"
            style={{
              background: currentPostIndex < currentPostIndexRef.current
                ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(0, 0, 0, 0.6) 100%)'
                : 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: currentPostIndex < currentPostIndexRef.current ? '1px solid rgba(249, 84, 0, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
              color: currentPostIndex < currentPostIndexRef.current ? '#fff' : 'rgba(255, 255, 255, 0.3)',
              cursor: currentPostIndex >= currentPostIndexRef.current ? 'not-allowed' : 'pointer',
              boxShadow: currentPostIndex < currentPostIndexRef.current ? '0 4px 12px rgba(0, 0, 0, 0.4), 0 0 16px rgba(249, 84, 0, 0.15)' : 'none'
            }}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <div
            ref={carouselRef}
            className="flex gap-3 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2"
            style={{
              overscrollBehaviorX: 'contain',  // Prevent momentum overshoot at boundaries
              scrollSnapStop: 'always',         // Force stop at each snap point
            }}
            onScroll={(e) => {
              // Skip if programmatic scrolling is in progress
              if (isScrollingRef.current) return;

              const container = e.currentTarget;
              const cardWidth = container.offsetWidth * 0.8;
              const gap = 12;
              const spacerWidth = container.offsetWidth * 0.1;
              const newIndex = Math.round((container.scrollLeft - spacerWidth) / (cardWidth + gap));

              // Update current index based on scroll position
              if (newIndex >= 0 && newIndex !== currentPostIndex) {
                updateEngageData({ currentPostIndex: newIndex });
              }
            }}
          >
            {/* Left spacer for centering first card */}
            <div className="flex-shrink-0 w-[10%]" />

            {session?.posts?.slice(0, engagedPosts.size + 1).map((post, index) => {
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
                  onMouseDown={(e) => {
                    // Use onMouseDown for faster response (fires before onClick)
                    // Only handle left click on center card for new engagements
                    if (e.button === 0 && isCenter && !isEngaged) {
                      e.preventDefault();
                      handleEngageClick(post);
                    }
                  }}
                  onClick={() => {
                    // Handle already-engaged cards (re-open link) and side card prevention
                    if (isCenter && isEngaged) {
                      openLink(getEngageUrl(post));
                      hapticFeedback('light');
                    }
                    // Side cards: no action
                  }}
                >
                  <div
                    className={`p-5 min-h-[160px] relative transition-all flex flex-col justify-start rounded-2xl overflow-hidden ${
                      isCenter ? 'cursor-pointer' : ''
                    }`}
                    style={{
                      background: isCenter
                        ? 'linear-gradient(135deg, rgba(249, 84, 0, 0.08) 0%, rgba(15, 10, 11, 0.85) 50%, rgba(249, 84, 0, 0.04) 100%)'
                        : 'linear-gradient(135deg, rgba(249, 84, 0, 0.03) 0%, rgba(15, 10, 11, 0.7) 50%, rgba(249, 84, 0, 0.02) 100%)',
                      backdropFilter: 'blur(32px) saturate(160%)',
                      WebkitBackdropFilter: 'blur(32px) saturate(160%)',
                      border: isCenter ? '1px solid rgba(249, 84, 0, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                      boxShadow: isCenter
                        ? '0 8px 32px rgba(0, 0, 0, 0.6), 0 0 20px rgba(249, 84, 0, 0.15), 0 1px 0 rgba(249, 84, 0, 0.1) inset'
                        : '0 4px 20px rgba(0, 0, 0, 0.4)'
                    }}
                  >
                    {/* Top right icons */}
                    <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
                      <XLogoIcon className="w-5 h-5 text-gray-400" />
                      <ExternalLinkIconFill className="w-5 h-5 text-[#f95400]" />
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
                                isEngaged ? 'ring-2 ring-[#f95400]/50' : ''
                              }`}
                            />
                          ) : (
                            <div className={`w-12 h-12 rounded-full gold-gradient-bg flex items-center justify-center ${
                              isEngaged ? 'ring-2 ring-[#f95400]/50' : ''
                            }`}>
                              <span className="text-lg font-bold text-black">
                                {(post.tweet_author_username || post.creator_x_username || post.creator).charAt(0).toUpperCase()}
                              </span>
                            </div>
                          )}
                          {/* Small clock on profile for pending (queued) posts */}
                          {isEngaged && (
                            <div className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-[#f95400] flex items-center justify-center border-2 border-black">
                              <ClockIconFill className="w-3 h-3 text-black" />
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

            {/* "Come back later" card at the end */}
            {/* Only show "all caught up" card when ALL posts are engaged */}
            {engagedPosts.size >= (session?.posts?.length || 0) && (
              <div
                className={`snap-center flex-shrink-0 transition-all duration-300 w-[80%] ${
                  currentPostIndex === (session?.posts?.length || 0)
                    ? 'scale-100 opacity-100'
                    : 'scale-95 opacity-50'
                }`}
              >
                <div className={`card-gold p-5 min-h-[160px] flex flex-col items-center justify-center text-center ${
                  currentPostIndex === (session?.posts?.length || 0) ? 'ring-2 ring-[#f95400]/50' : ''
                }`}>
                  <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center mb-4">
                    <ClockIconFill className="w-8 h-8 text-gray-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">You're all caught up!</h3>
                  <p className="text-gray-400 text-sm">Come back later for more posts to engage with</p>
                </div>
              </div>
            )}

            {/* Right spacer for centering last card */}
            <div className="flex-shrink-0 w-[10%]" />
          </div>
          </div>{/* End of cards + nav buttons wrapper */}

          {/* Scroll indicators - only show for rendered cards */}
          <div className="flex justify-center gap-1.5 mt-3">
            {session?.posts?.slice(0, engagedPosts.size + 1).map((_, index) => (
              <div
                key={index}
                className={`h-1.5 rounded-full transition-all ${
                  index === currentPostIndex
                    ? 'w-6 bg-[#f95400]'
                    : engagedPosts.size > index
                      ? 'w-1.5 bg-[#f95400]/50'
                      : 'w-1.5 bg-gray-600'
                }`}
              />
            ))}
            {/* Show end indicator only when all posts engaged */}
            {engagedPosts.size >= (session?.posts?.length || 0) && (
              <div
                className={`h-1.5 rounded-full transition-all ${
                  currentPostIndex === session?.posts?.length
                    ? 'w-6 bg-[#f95400]'
                    : 'w-1.5 bg-[#f95400]/50'
                }`}
              />
            )}
          </div>

          {/* Action Buttons - Claim and Submit side by side */}
          <div className="mt-4 flex gap-3 relative">
            <button
              onClick={() => {
                if (engagedPosts.size >= 10 && !isClaimLoading && !hasProcessingBatch) {
                  hapticFeedback('medium');
                  completeSession();
                } else if (engagedPosts.size < 10) {
                  hapticFeedback('error');
                  // Show tooltip
                  if (claimTooltipTimeoutRef.current) {
                    clearTimeout(claimTooltipTimeoutRef.current);
                  }
                  setShowClaimTooltip(true);
                  claimTooltipTimeoutRef.current = setTimeout(() => {
                    setShowClaimTooltip(false);
                  }, 2000);
                }
              }}
              disabled={engagedPosts.size < 10 || isClaimLoading || hasProcessingBatch}
              className="flex-1 h-12 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-95"
              style={{
                background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(249, 84, 0, 0.4)',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
                color: 'white',
              }}
            >
              {isClaimLoading ? (
                <>
                  <ClockIconFill className="w-5 h-5 text-white" />
                  Queuing...
                </>
              ) : hasProcessingBatch ? (
                <>
                  <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <BoltIconFill className="w-5 h-5 text-white" />
                  {engagedPosts.size >= 10 ? 'Claim' : `${engagedPosts.size}/10`}
                </>
              )}
            </button>
            <button
              onClick={() => {
                hapticFeedback('light');
                setShowSubmitModal(true);
              }}
              className="flex-1 h-12 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-95"
              style={{
                background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(249, 84, 0, 0.4)',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
                color: 'white',
              }}
            >
              <SendIconFill className="w-5 h-5 text-white" />
              Submit
            </button>

            {/* Claim tooltip message */}
            <div
              className={`absolute -top-12 left-0 right-0 flex justify-center transition-all duration-300 ${
                showClaimTooltip ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
              }`}
            >
              <div
                className="px-4 py-2 rounded-xl text-sm text-white/90"
                style={{
                  background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(15, 10, 11, 0.9) 100%)',
                  backdropFilter: 'blur(16px)',
                  border: '1px solid rgba(249, 84, 0, 0.3)',
                }}
              >
                Minimum 10 queues to claim
              </div>
            </div>
          </div>

          {/* Claim History - shows queued verification batches */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-400">Verification Queue</h4>
              {hasProcessingBatch && (
                <span className="flex items-center gap-1.5 text-xs text-yellow-500">
                  <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-pulse" />
                  Processing
                </span>
              )}
            </div>
            <div className="glass-card p-3 space-y-2 max-h-48 overflow-y-auto">
              {claimHistory.length > 0 ? (
                claimHistory.slice(0, 5).map((batch) => (
                  <div
                    key={batch.id}
                    className="flex items-center justify-between p-2.5 bg-white/[0.03] rounded-xl border border-white/[0.05]"
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        batch.status === 'completed' && batch.credits_awarded && batch.credits_awarded > 0
                          ? 'bg-[#f95400]/20'
                          : batch.status === 'pending' || batch.status === 'processing'
                          ? 'bg-yellow-500/20'
                          : 'bg-white/[0.05]'
                      }`}>
                        {(batch.status === 'pending' || batch.status === 'processing') ? (
                          <ClockIconFill className="w-4 h-4 text-yellow-500" />
                        ) : batch.status === 'completed' && batch.credits_awarded && batch.credits_awarded > 0 ? (
                          <CheckIconFill className="w-4 h-4 text-[#f95400]" />
                        ) : (
                          <InfoIconFill className="w-4 h-4 text-gray-500" />
                        )}
                      </div>
                      <div>
                        <p className="text-xs text-white">{batch.engagement_count} engagements</p>
                        <p className="text-[10px] text-gray-500">
                          {new Date(batch.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      {(batch.status === 'pending' || batch.status === 'processing') && (
                        <span className="text-yellow-500 text-xs">Verifying...</span>
                      )}
                      {batch.status === 'completed' && batch.credits_awarded !== null && batch.credits_awarded > 0 && (
                        <span className="text-[#f95400] text-sm font-semibold">
                          +{Number(batch.credits_awarded).toFixed(2)}
                        </span>
                      )}
                      {batch.status === 'completed' && (batch.credits_awarded === null || batch.credits_awarded === 0) && (
                        <span className="text-gray-500 text-xs">{batch.failed || 0} failed</span>
                      )}
                      {batch.status === 'failed' && (
                        <span className="text-red-400 text-xs">Error</span>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-4">
                  <div className="glass-icon glass-icon-md mx-auto mb-2">
                    <ClockIconFill className="w-5 h-5 text-gray-500" />
                  </div>
                  <p className="text-xs text-gray-500">No recent claims</p>
                  <p className="text-[10px] text-gray-600 mt-1">Engage with 10 posts to claim</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <SubmitModal
        isOpen={showSubmitModal}
        onClose={() => setShowSubmitModal(false)}
        user={user}
        onUserUpdate={onUserUpdate}
        settings={settings}
      />

      {/* Verification Results Popup - shown when verification completes */}
      {showFailurePopup && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-sm bg-black/95 border border-[#f95400]/30 rounded-2xl p-6 text-center shadow-2xl shadow-black/50">
            {/* Icon */}
            <div className={`w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center ${
              failedCount > 0 ? 'bg-yellow-500/20' : 'bg-[#f95400]/20'
            }`}>
              {failedCount > 0 ? (
                <InfoIconFill className="w-10 h-10 text-yellow-500" />
              ) : (
                <CheckIconFill className="w-10 h-10 text-[#f95400]" />
              )}
            </div>

            {/* Title */}
            <h3 className="text-xl font-bold mb-2">
              {failedCount > 0 ? 'Verification Complete' : 'All Verified!'}
            </h3>

            {/* Earned Karma - always show if earned */}
            {earnedKarma > 0 && (
              <div className="mb-4">
                <span className="text-3xl font-bold gold-gradient-text">+{formatKarma(earnedKarma)}</span>
                <span className="text-gray-400 ml-2">karma earned</span>
              </div>
            )}

            {/* Failed count message */}
            {failedCount > 0 && (
              <p className="text-gray-400 mb-4 text-sm">
                {failedCount} post{failedCount !== 1 ? 's' : ''} couldn't be verified and {failedCount !== 1 ? 'have' : 'has'} been removed.
              </p>
            )}

            {/* Continue button */}
            <button
              onClick={async () => {
                setShowFailurePopup(false);
                // Light refresh - fetch new cards without full loading state
                try {
                  const data = await api.startSession();
                  if (data.posts.length > 0) {
                    engagedPostsRef.current = new Set<string>();
                    currentPostIndexRef.current = 0;
                    updateEngageData({
                      session: data,
                      engagedPosts: new Set<string>(),
                      currentPostIndex: 0,
                      lastFetchedAt: Date.now(),
                    });
                    // Scroll to first card
                    if (carouselRef.current) {
                      carouselRef.current.scrollTo({ left: 0, behavior: 'instant' });
                    }
                  }
                } catch (err) {
                  console.error('Failed to refresh cards:', err);
                }
              }}
              className="btn-primary w-full"
            >
              Continue Engaging
            </button>
          </div>
        </div>
      )}

      {/* Engage Info Modal */}
      {showEngageInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setShowEngageInfo(false)}
          />

          {/* Modal */}
          <div
            className="relative w-full max-w-sm rounded-2xl p-5 animate-slide-up"
            style={{
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
              backdropFilter: 'blur(32px) saturate(160%)',
              WebkitBackdropFilter: 'blur(32px) saturate(160%)',
              border: '1px solid rgba(249, 84, 0, 0.15)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center"
                  style={{
                    background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(249, 84, 0, 0.08) 100%)',
                    border: '1px solid rgba(249, 84, 0, 0.3)',
                  }}
                >
                  <BoltIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
                </div>
                <h3 className="text-base font-semibold text-white">What is Karma?</h3>
              </div>
              <button
                onClick={() => setShowEngageInfo(false)}
                className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:bg-white/10"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
              >
                <XIconFill className="w-4 h-4 text-gray-400" />
              </button>
            </div>

            {/* Content */}
            <div className="space-y-3 mb-5">
              <p className="text-sm text-gray-400">
                <span className="text-[#f95400] font-medium">1.</span> <span className="text-white font-medium">Boost your posts</span> by spending karma to get engagements
              </p>
              <p className="text-sm text-gray-400">
                <span className="text-[#f95400] font-medium">2.</span> <span className="text-white font-medium">Join USDT raffles</span> by using karma in Earn section, requires engagement on XP posts (Partner posts)
              </p>
              <p className="text-sm text-gray-400">
                <span className="text-[#f95400] font-medium">3.</span> <span className="text-white font-medium">Join token giveaways</span> on the Earn section
              </p>
            </div>

            {/* Note */}
            <p className="text-xs text-gray-500 text-center">
              Engage with posts to earn <span className="text-[#f95400]">karma</span>, the currency of Loudrr
            </p>
          </div>
        </div>
      )}
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

  // Glass card style matching Stats modal
  const glassCardStyle = {
    background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
    backdropFilter: 'blur(32px) saturate(160%)',
    WebkitBackdropFilter: 'blur(32px) saturate(160%)',
    border: '1px solid rgba(249, 84, 0, 0.15)',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset'
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg rounded-t-3xl max-h-[85vh] flex flex-col animate-slide-up"
        style={{
          background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.95) 50%, rgba(249, 84, 0, 0.02) 100%)',
          backdropFilter: 'blur(32px) saturate(160%)',
          WebkitBackdropFilter: 'blur(32px) saturate(160%)',
          border: '1px solid rgba(249, 84, 0, 0.2)',
          borderBottom: 'none',
          boxShadow: '0 -4px 40px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.1) inset'
        }}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-[#f95400]/40" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-4 pb-4 border-b border-[#f95400]/15">
          <div>
            <h2 className="text-xl font-bold">Submit Post</h2>
            <p className="text-gray-400 text-sm">Share your X post to get engagements</p>
          </div>
          <button
            onClick={handleClose}
            className="w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:bg-white/10"
            style={{ background: 'rgba(0, 0, 0, 0.3)' }}
          >
            <XIconFill className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Karma Selection */}
          <div className="p-4 space-y-4 rounded-2xl" style={glassCardStyle}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Karma to Spend</p>
                <p className="text-2xl font-bold gold-gradient-text">{formatKarma(karmaAmount)}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">Your Balance</p>
                <p className={`text-xl font-bold ${canSubmit ? 'gold-gradient-text' : 'text-gray-500'}`}>
                  {formatKarma(user?.credits || 0)}
                </p>
              </div>
            </div>

            {/* Karma Slider - dynamic based on minCost/maxCost from settings */}
            <div className="space-y-2">
              <input
                type="range"
                min={minCost}
                max={maxCost}
                step={5}
                value={karmaAmount}
                onChange={(e) => {
                  hapticFeedback('light');
                  setKarmaAmount(Number(e.target.value));
                }}
                className="w-full h-2 bg-black/50 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#f95400] [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-[#f95400]/30 [&::-webkit-slider-thumb]:cursor-grab [&::-webkit-slider-thumb]:active:cursor-grabbing"
                disabled={submitting}
              />
              {/* Number labels */}
              <div className="flex justify-between px-[2px]">
                {Array.from({ length: Math.floor((maxCost - minCost) / 5) + 1 }, (_, i) => minCost + i * 5).map((amount) => (
                  <button
                    key={amount}
                    type="button"
                    onClick={() => {
                      hapticFeedback('light');
                      setKarmaAmount(amount);
                    }}
                    disabled={submitting}
                    className={`text-xs transition-all ${karmaAmount === amount ? 'text-[#f95400] font-semibold' : 'text-gray-500'}`}
                  >
                    {amount}
                  </button>
                ))}
              </div>
            </div>

            <p className="text-xs text-gray-500 text-center">
              Higher karma = more engagements · Rewards based on engager tiers
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
                className="w-full px-4 py-3 rounded-xl text-white placeholder-gray-500 transition-all focus:outline-none focus:ring-2 focus:ring-[#f95400]/50"
                style={{
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(249, 84, 0, 0.2)',
                }}
                disabled={submitting}
              />
            </div>

            {error && (
              <div className="rounded-xl p-4" style={{ ...glassCardStyle, border: '1px solid rgba(249, 84, 0, 0.3)' }}>
                <p className="text-[#f95400] text-sm">{error}</p>
              </div>
            )}

            {result?.success && (
              <div className="rounded-xl p-4" style={{ ...glassCardStyle, border: '1px solid rgba(249, 84, 0, 0.4)' }}>
                <p className="text-[#f95400] text-sm">{result.message}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={!canSubmit || !xLink.trim() || submitting}
              className="w-full h-12 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-50"
              style={{
                background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(255, 140, 66, 0.15) 50%, rgba(249, 84, 0, 0.18) 100%)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(249, 84, 0, 0.4)',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 140, 66, 0.2) inset',
                color: 'white',
              }}
            >
              {submitting ? 'Submitting...' : 'Submit Post'}
            </button>
          </form>

          {!canSubmit && user && (
            <div className="p-4 rounded-2xl" style={{ ...glassCardStyle, border: '1px solid rgba(249, 84, 0, 0.25)' }}>
              <p className="text-sm text-gray-300">
                You need <span className="gold-gradient-text font-semibold">{formatKarma(karmaAmount - user.credits)} more karma</span> to submit a post.
                Engage with posts to earn karma!
              </p>
            </div>
          )}

          {/* How it works */}
          <div className="space-y-3 pb-2">
            <h3 className="text-sm font-semibold text-gray-400">How it works</h3>
            <div className="space-y-2">
              {[
                `Select how much karma to spend (${minCost}-${maxCost})`,
                'Other users engage with your post',
                'They earn karma based on their tier until yours is depleted',
              ].map((text, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{ background: 'rgba(249, 84, 0, 0.15)', border: '1px solid rgba(249, 84, 0, 0.3)' }}
                  >
                    <span className="text-xs gold-gradient-text">{i + 1}</span>
                  </div>
                  <p className="text-sm text-gray-400">{text}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Tier note */}
          <p className="text-xs text-gray-500 text-center pb-4">
            Your karma is spent based on engager tiers. Same tier users are prioritized to balance your engagements.
          </p>
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

  // Glass card style
  const glassCardStyle = {
    background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.04) 0%, rgba(15, 10, 11, 0.8) 50%, rgba(249, 84, 0, 0.02) 100%)',
    backdropFilter: 'blur(32px) saturate(160%)',
    WebkitBackdropFilter: 'blur(32px) saturate(160%)',
    border: '1px solid rgba(249, 84, 0, 0.15)',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(249, 84, 0, 0.08) inset'
  };

  // Glass bar style
  const glassBarStyle = {
    background: 'rgba(255, 255, 255, 0.08)',
    borderRadius: '6px',
  };

  const barFillStyle = {
    background: 'linear-gradient(180deg, #ff8c42 0%, #f95400 100%)',
    borderRadius: '6px',
    boxShadow: '0 0 12px rgba(249, 84, 0, 0.4)',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg max-h-[85vh] flex flex-col animate-slide-up rounded-t-3xl overflow-hidden"
        style={{
          background: 'linear-gradient(180deg, rgba(15, 10, 11, 0.98) 0%, rgba(10, 10, 10, 0.99) 100%)',
          backdropFilter: 'blur(40px)',
          WebkitBackdropFilter: 'blur(40px)',
          border: '1px solid rgba(249, 84, 0, 0.2)',
          borderBottom: 'none',
          boxShadow: '0 -8px 32px rgba(0, 0, 0, 0.8), 0 0 60px rgba(249, 84, 0, 0.05)'
        }}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-gradient-to-r from-[#f95400]/40 via-[#ff8c42]/60 to-[#f95400]/40" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pb-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="glass-icon glass-icon-md">
              <ChartIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Your Stats</h2>
              <p className="text-gray-400 text-sm">Lifetime performance</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 rounded-full flex items-center justify-center transition-all active:scale-95"
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <XIconFill className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Loading State - Full modal */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-[#f95400]/30 border-t-[#f95400] rounded-full animate-spin" />
          </div>
        ) : error || !stats ? (
          <div className="flex-1 flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4" style={{
              background: 'rgba(255, 255, 255, 0.05)',
            }}>
              <XIconFill className="w-8 h-8 text-gray-500" />
            </div>
            <p className="text-gray-400 mb-4">{error || 'Could not load stats'}</p>
            <button onClick={loadStats} className="btn-primary px-6 py-3">Retry</button>
          </div>
        ) : (
          /* Scrollable Content */
          <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
              {/* Karma Flow & Engagements - Side by Side */}
              <div className="grid grid-cols-2 gap-3">
                {/* Karma Flow */}
                <div className="p-4 pb-3 rounded-2xl" style={glassCardStyle}>
                  <h3 className="flex items-center gap-2 text-xs font-semibold text-gray-300 mb-5">
                    <TrendingUpIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
                    Karma Flow
                  </h3>
                  <div className="flex items-end justify-center gap-8">
                    <div className="flex flex-col items-center">
                      <div className="w-9 h-14 flex items-end rounded-md overflow-hidden" style={glassBarStyle}>
                        <div
                          className="w-full transition-all duration-500"
                          style={{ ...barFillStyle, height: `${earnedHeight}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">Earned</p>
                      <p className="text-sm font-bold" style={{ color: '#ff8c42' }}>{formatKarma(stats.user.total_credits_earned)}</p>
                    </div>
                    <div className="flex flex-col items-center">
                      <div className="w-9 h-14 flex items-end rounded-md overflow-hidden" style={glassBarStyle}>
                        <div
                          className="w-full transition-all duration-500 opacity-60"
                          style={{ ...barFillStyle, height: `${spentHeight}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">Spent</p>
                      <p className="text-sm font-bold text-gray-300">{formatKarma(stats.user.total_credits_spent)}</p>
                    </div>
                  </div>
                </div>

                {/* Engagements */}
                <div className="p-4 pb-3 rounded-2xl" style={glassCardStyle}>
                  <h3 className="flex items-center gap-2 text-xs font-semibold text-gray-300 mb-5">
                    <BoltIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
                    Engagements
                  </h3>
                  <div className="flex items-end justify-center gap-8">
                    <div className="flex flex-col items-center">
                      <div className="w-9 h-14 flex items-end rounded-md overflow-hidden" style={glassBarStyle}>
                        <div
                          className="w-full transition-all duration-500"
                          style={{ ...barFillStyle, height: `${givenHeight}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">Given</p>
                      <p className="text-sm font-bold" style={{ color: '#ff8c42' }}>{stats.engagements.given}</p>
                    </div>
                    <div className="flex flex-col items-center">
                      <div className="w-9 h-14 flex items-end rounded-md overflow-hidden" style={glassBarStyle}>
                        <div
                          className="w-full transition-all duration-500"
                          style={{ ...barFillStyle, height: `${receivedHeight}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">Received</p>
                      <p className="text-sm font-bold" style={{ color: '#ff8c42' }}>{stats.engagements.received}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Posts Stats */}
              <div className="p-4 rounded-2xl" style={glassCardStyle}>
                <div className="flex items-center gap-2 mb-4">
                  <SendIconFill className="w-4 h-4" style={ICON_GRADIENT_STYLE} />
                  <h3 className="text-sm font-semibold text-gray-300">Your Posts</h3>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#ff8c42' }}>{stats.posts.total}</p>
                    <p className="text-xs text-gray-400">Total</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#ff8c42' }}>{stats.posts.active}</p>
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
                  <h3 className="text-sm font-semibold text-gray-300 px-1">Recent Posts</h3>
                  {stats.recent_posts.map((post) => (
                    <div key={post.id} className="p-4 rounded-2xl" style={glassCardStyle}>
                      <div className="flex items-center justify-between mb-2">
                        <span
                          className="px-2 py-0.5 rounded-full text-xs font-medium"
                          style={{
                            background: post.status === 'active' ? 'rgba(249, 84, 0, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                            color: post.status === 'active' ? '#ff8c42' : 'rgba(255, 255, 255, 0.5)',
                            border: post.status === 'active' ? '1px solid rgba(249, 84, 0, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
                          }}
                        >
                          {post.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(post.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-300 truncate mb-3">{post.x_link}</p>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            background: 'linear-gradient(90deg, #f95400 0%, #ff8c42 100%)',
                            boxShadow: '0 0 8px rgba(249, 84, 0, 0.3)',
                            width: `${post.engagement_progress}%`
                          }}
                        />
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        {post.engagement_progress}% complete • {formatKarma(post.escrow_remaining)} karma remaining
                      </p>
                    </div>
                  ))}
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
}

// ONBOARDING SCREEN - shown for new whitelisted users
function OnboardingScreen({
  user,
  onComplete,
}: {
  user: User;
  onComplete: () => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await api.completeOnboarding();
      hapticFeedback('success');

      // Refetch user to get updated data
      await onComplete();
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
      hapticFeedback('error');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center p-6">
      {/* Logo */}
      <div className="mb-6">
        <img
          src="/loudrr-icon.png"
          alt="Loudrr"
          className="w-20 h-20"
        />
      </div>

      {/* Welcome Message */}
      <h1 className="text-3xl font-bold text-white mb-2 text-center">
        Welcome to Loudrr!
      </h1>

      <p className="text-gray-400 text-center mb-8 max-w-sm">
        Your multiplier is connected to your X account score.<br />
        Higher score = More karma per engagement.
      </p>

      {/* X Username Display */}
      {user.x_username && (
        <div className="mb-8 px-6 py-3 rounded-xl bg-white/5 border border-[#f95400]/30">
          <span className="text-[#f95400] font-medium">@{user.x_username}</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-red-400 text-sm mb-4">{error}</p>
      )}

      {/* Start Button */}
      <button
        onClick={handleStart}
        disabled={loading}
        className="px-8 py-4 btn-primary text-lg flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
            Loading...
          </>
        ) : (
          <>Let's Go Loudrr</>
        )}
      </button>

      {/* Footer */}
      <p className="mt-8 text-gray-600 text-sm text-center">
        Earn karma by engaging.<br />
        Spend karma to grow.
      </p>
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
      <div className="relative w-full max-w-sm bg-zinc-900/95 backdrop-blur-xl rounded-2xl border border-[#f95400]/30 p-6 animate-slide-up">
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
            className="w-full bg-black/50 border border-gray-700 rounded-xl py-3 pl-8 pr-4 text-white placeholder-gray-500 focus:border-[#f95400]/50 focus:outline-none transition-colors"
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
          className="w-full py-3 rounded-xl bg-[#f95400] text-black font-semibold disabled:opacity-50 hover:bg-[#E56000] transition-colors"
        >
          {loading ? 'Verifying...' : 'Link Account'}
        </button>
      </div>
    </div>
  );
}

// FILLED ICONS
function HomeIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.47 3.84a.75.75 0 011.06 0l8.69 8.69a.75.75 0 101.06-1.06l-8.689-8.69a2.25 2.25 0 00-3.182 0l-8.69 8.69a.75.75 0 001.061 1.06l8.69-8.69z" />
      <path d="M12 5.432l8.159 8.159c.03.03.06.058.091.086v6.198c0 1.035-.84 1.875-1.875 1.875H15a.75.75 0 01-.75-.75v-4.5a.75.75 0 00-.75-.75h-3a.75.75 0 00-.75.75V21a.75.75 0 01-.75.75H5.625a1.875 1.875 0 01-1.875-1.875v-6.198a2.29 2.29 0 00.091-.086L12 5.43z" />
    </svg>
  );
}

function HomeIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
    </svg>
  );
}

function BoltIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M14.615 1.595a.75.75 0 01.359.852L12.982 9.75h7.268a.75.75 0 01.548 1.262l-10.5 11.25a.75.75 0 01-1.272-.71l1.992-7.302H3.75a.75.75 0 01-.548-1.262l10.5-11.25a.75.75 0 01.913-.143z" clipRule="evenodd" />
    </svg>
  );
}

function BoltIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

function PlusIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zM12.75 9a.75.75 0 00-1.5 0v2.25H9a.75.75 0 000 1.5h2.25V15a.75.75 0 001.5 0v-2.25H15a.75.75 0 000-1.5h-2.25V9z" clipRule="evenodd" />
    </svg>
  );
}

function PlusIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ChartIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.375 2.25c-1.035 0-1.875.84-1.875 1.875v15.75c0 1.035.84 1.875 1.875 1.875h.75c1.035 0 1.875-.84 1.875-1.875V4.125c0-1.036-.84-1.875-1.875-1.875h-.75zM9.75 8.625c0-1.036.84-1.875 1.875-1.875h.75c1.036 0 1.875.84 1.875 1.875v11.25c0 1.035-.84 1.875-1.875 1.875h-.75a1.875 1.875 0 01-1.875-1.875V8.625zM3 13.125c0-1.036.84-1.875 1.875-1.875h.75c1.036 0 1.875.84 1.875 1.875v6.75c0 1.035-.84 1.875-1.875 1.875h-.75A1.875 1.875 0 013 19.875v-6.75z" />
    </svg>
  );
}

function ChartIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function WalletIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M2.273 5.625A4.483 4.483 0 015.25 4.5h13.5c1.141 0 2.183.425 2.977 1.125A3 3 0 0018.75 3H5.25a3 3 0 00-2.977 2.625zM2.273 8.625A4.483 4.483 0 015.25 7.5h13.5c1.141 0 2.183.425 2.977 1.125A3 3 0 0018.75 6H5.25a3 3 0 00-2.977 2.625zM5.25 9a3 3 0 00-3 3v6a3 3 0 003 3h13.5a3 3 0 003-3v-6a3 3 0 00-3-3H15a.75.75 0 00-.75.75 2.25 2.25 0 01-4.5 0A.75.75 0 009 9H5.25z" />
    </svg>
  );
}

function FireIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12.963 2.286a.75.75 0 00-1.071-.136 9.742 9.742 0 00-3.539 6.177A7.547 7.547 0 016.648 6.61a.75.75 0 00-1.152.082A9 9 0 1015.68 4.534a7.46 7.46 0 01-2.717-2.248zM15.75 14.25a3.75 3.75 0 11-7.313-1.172c.628.465 1.35.81 2.133 1a5.99 5.99 0 011.925-3.545 3.75 3.75 0 013.255 3.717z" clipRule="evenodd" />
    </svg>
  );
}

function FireIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.047 8.287 8.287 0 009 9.601a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 18a3.75 3.75 0 00.495-7.468 5.99 5.99 0 00-1.925 3.547 5.975 5.975 0 01-2.133-1.001A3.75 3.75 0 0012 18z" />
    </svg>
  );
}

function TrophyIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M5.166 2.621v.858c-1.035.148-2.059.33-3.071.543a.75.75 0 00-.584.859 6.753 6.753 0 006.138 5.6 6.73 6.73 0 002.743 1.346A6.707 6.707 0 019.279 15H8.54c-1.036 0-1.875.84-1.875 1.875V19.5h-.75a2.25 2.25 0 00-2.25 2.25c0 .414.336.75.75.75h15a.75.75 0 00.75-.75 2.25 2.25 0 00-2.25-2.25h-.75v-2.625c0-1.036-.84-1.875-1.875-1.875h-.739a6.706 6.706 0 01-1.112-3.173 6.73 6.73 0 002.743-1.347 6.753 6.753 0 006.139-5.6.75.75 0 00-.585-.858 47.077 47.077 0 00-3.07-.543V2.62a.75.75 0 00-.658-.744 49.22 49.22 0 00-6.093-.377c-2.063 0-4.096.128-6.093.377a.75.75 0 00-.657.744zm0 2.629c0 1.196.312 2.32.857 3.294A5.266 5.266 0 013.16 5.337a45.6 45.6 0 012.006-.343v.256zm13.5 0v-.256c.674.1 1.343.214 2.006.343a5.265 5.265 0 01-2.863 3.207 6.72 6.72 0 00.857-3.294z" clipRule="evenodd" />
    </svg>
  );
}

function CheckIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
    </svg>
  );
}

function HeartIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.645 20.91l-.007-.003-.022-.012a15.247 15.247 0 01-.383-.218 25.18 25.18 0 01-4.244-3.17C4.688 15.36 2.25 12.174 2.25 8.25 2.25 5.322 4.714 3 7.688 3A5.5 5.5 0 0112 5.052 5.5 5.5 0 0116.313 3c2.973 0 5.437 2.322 5.437 5.25 0 3.925-2.438 7.111-4.739 9.256a25.175 25.175 0 01-4.244 3.17 15.247 15.247 0 01-.383.219l-.022.012-.007.004-.003.001a.752.752 0 01-.704 0l-.003-.001z" />
    </svg>
  );
}

function XIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clipRule="evenodd" />
    </svg>
  );
}

function ExternalLinkIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M15.75 2.25H21a.75.75 0 01.75.75v5.25a.75.75 0 01-1.5 0V4.81l-8.97 8.97a.75.75 0 01-1.06-1.06l8.97-8.97h-3.44a.75.75 0 010-1.5zm-10.5 4.5a1.5 1.5 0 00-1.5 1.5v10.5a1.5 1.5 0 001.5 1.5h10.5a1.5 1.5 0 001.5-1.5V10.5a.75.75 0 011.5 0v8.25a3 3 0 01-3 3H5.25a3 3 0 01-3-3V8.25a3 3 0 013-3h8.25a.75.75 0 010 1.5H5.25z" clipRule="evenodd" />
    </svg>
  );
}

function InfoIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 01.67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 11-.671-1.34l.041-.022zM12 9a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
    </svg>
  );
}

function InfoIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
    </svg>
  );
}

function CheckIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function XLogoIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function ChevronDownIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function ChevronDownIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
    </svg>
  );
}

function ChevronRightIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

function ChevronRightIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
    </svg>
  );
}

function ClockIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ClockIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
    </svg>
  );
}

function DiscordIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" />
    </svg>
  );
}

function TelegramIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  );
}

function SparklesIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M9 4.5a.75.75 0 01.721.544l.813 2.846a3.75 3.75 0 002.576 2.576l2.846.813a.75.75 0 010 1.442l-2.846.813a3.75 3.75 0 00-2.576 2.576l-.813 2.846a.75.75 0 01-1.442 0l-.813-2.846a3.75 3.75 0 00-2.576-2.576l-2.846-.813a.75.75 0 010-1.442l2.846-.813A3.75 3.75 0 007.466 7.89l.813-2.846A.75.75 0 019 4.5zM18 1.5a.75.75 0 01.728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 010 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 01-1.456 0l-.258-1.036a2.625 2.625 0 00-1.91-1.91l-1.036-.258a.75.75 0 010-1.456l1.036-.258a2.625 2.625 0 001.91-1.91l.258-1.036A.75.75 0 0118 1.5zM16.5 15a.75.75 0 01.712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 010 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 01-1.422 0l-.395-1.183a1.5 1.5 0 00-.948-.948l-1.183-.395a.75.75 0 010-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0116.5 15z" clipRule="evenodd" />
    </svg>
  );
}

function CalendarIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  );
}

function MegaphoneIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M16.881 4.346A23.112 23.112 0 018.25 6H7.5a5.25 5.25 0 00-.88 10.427 21.593 21.593 0 001.378 3.94c.464 1.004 1.674 1.32 2.582.796l.657-.379c.88-.508 1.165-1.592.772-2.468a17.116 17.116 0 01-.628-1.607c1.918.258 3.76.75 5.5 1.446A21.727 21.727 0 0018 11.25c0-2.413-.393-4.735-1.119-6.904zM18.26 3.74a23.22 23.22 0 011.24 7.51 23.22 23.22 0 01-1.24 7.51c-.055.161-.111.322-.17.482a.75.75 0 101.409.516 24.555 24.555 0 001.415-6.43 2.992 2.992 0 00.836-2.078c0-.806-.319-1.54-.836-2.078a24.65 24.65 0 00-1.415-6.43.75.75 0 10-1.409.516c.059.16.116.321.17.483z" />
    </svg>
  );
}

function MegaphoneIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 01-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 018.835 2.535M10.34 6.66a23.847 23.847 0 008.835-2.535m0 0A23.74 23.74 0 0018.795 3m.38 1.125a23.91 23.91 0 011.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 001.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 010 3.46" />
    </svg>
  );
}

function GiftIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M9.375 3a1.875 1.875 0 000 3.75h1.875v4.5H3.375A1.875 1.875 0 011.5 9.375v-.75c0-1.036.84-1.875 1.875-1.875h3.193A3.375 3.375 0 0112 2.753a3.375 3.375 0 015.432 3.997h3.193c1.035 0 1.875.84 1.875 1.875v.75c0 1.036-.84 1.875-1.875 1.875H12.75v-4.5h1.875a1.875 1.875 0 10-1.875-1.875V6.75h-1.5V4.875C11.25 3.839 10.41 3 9.375 3zM11.25 12.75H3v6.75a2.25 2.25 0 002.25 2.25h6v-9zM12.75 12.75v9h6a2.25 2.25 0 002.25-2.25v-6.75h-8.25z" />
    </svg>
  );
}

function GiftIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 11.25v8.25a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 109.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1114.625 7.5H12m0 0V21m-8.625-9.75h18c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125h-18c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
    </svg>
  );
}

// Loud tab icons (rocket boost)
function RocketIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M9.315 7.584C12.195 3.883 16.695 1.5 21.75 1.5a.75.75 0 01.75.75c0 5.056-2.383 9.555-6.084 12.436A6.75 6.75 0 019.75 22.5a.75.75 0 01-.75-.75v-4.131A15.838 15.838 0 016.382 15H2.25a.75.75 0 01-.75-.75 6.75 6.75 0 017.815-6.666zM15 6.75a2.25 2.25 0 100 4.5 2.25 2.25 0 000-4.5z" clipRule="evenodd" />
      <path d="M5.26 17.242a.75.75 0 10-.897-1.203 5.243 5.243 0 00-2.05 5.022.75.75 0 00.625.627 5.243 5.243 0 005.022-2.051.75.75 0 10-1.202-.897 3.744 3.744 0 01-3.008 1.51c0-1.23.592-2.323 1.51-3.008z" />
    </svg>
  );
}

function TrendingUpIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z" clipRule="evenodd" />
    </svg>
  );
}

function RocketIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
    </svg>
  );
}

// Send/Arrow icon for Submit
function SendIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" />
    </svg>
  );
}

function SendIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.125A59.768 59.768 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5" />
    </svg>
  );
}

// Speaker/Volume wave for LOUD
function SpeakerWaveIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.35 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM18.584 5.106a.75.75 0 011.06 0c3.808 3.807 3.808 9.98 0 13.788a.75.75 0 11-1.06-1.06 8.25 8.25 0 000-11.668.75.75 0 010-1.06z" />
      <path d="M15.932 7.757a.75.75 0 011.061 0 6 6 0 010 8.486.75.75 0 01-1.06-1.061 4.5 4.5 0 000-6.364.75.75 0 010-1.06z" />
    </svg>
  );
}

function SpeakerWaveIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
    </svg>
  );
}

// Star icon for Earn
function StarIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.006 5.404.434c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.434 2.082-5.005z" clipRule="evenodd" />
    </svg>
  );
}

function StarIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.562.562 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
    </svg>
  );
}

// Target/Bullseye icon for Campaigns
function TargetIconFill({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zM12 6a.75.75 0 01.75.75v.5a4.752 4.752 0 013.75 3.75h.5a.75.75 0 010 1.5h-.5a4.752 4.752 0 01-3.75 3.75v.5a.75.75 0 01-1.5 0v-.5a4.752 4.752 0 01-3.75-3.75h-.5a.75.75 0 010-1.5h.5A4.752 4.752 0 0111.25 7.25v-.5A.75.75 0 0112 6zm0 3.75a2.25 2.25 0 100 4.5 2.25 2.25 0 000-4.5z" clipRule="evenodd" />
    </svg>
  );
}

function TargetIcon({ className = "w-6 h-6", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15a3 3 0 100-6 3 3 0 000 6z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9V6m0 9v3M9 12H6m9 0h3" />
    </svg>
  );
}

// =============================================================================
// LOUD TAB - UGC Rewards Feature (Premium UX with Horizontal Cards)
// =============================================================================

function LoudTab({ user: _user }: { user: User | null }) {
  const [projectsData, setProjectsData] = useState<LoudProjectsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<LoudProject | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<LoudLeaderboardResponse | null>(null);
  const [loadingLeaderboard, setLoadingLeaderboard] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [successToast, setSuccessToast] = useState<{ points: number; rank: number } | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    // Auto-select first project on load
    if (projectsData?.projects.length && !selectedProject) {
      setSelectedProject(projectsData.projects[0]);
    }
  }, [projectsData]);

  useEffect(() => {
    // Load leaderboard when project is selected
    if (selectedProject) {
      loadLeaderboard(selectedProject.slug);
    }
  }, [selectedProject]);

  const loadProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await loudApi.getProjects();
      setProjectsData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const loadLeaderboard = async (slug: string) => {
    try {
      setLoadingLeaderboard(true);
      const data = await loudApi.getLeaderboard(slug);
      setLeaderboardData(data);
    } catch (err) {
      console.error('Failed to load leaderboard:', err);
    } finally {
      setLoadingLeaderboard(false);
    }
  };

  const formatTimeRemaining = (hours: number): string => {
    if (hours < 24) return `${hours}h left`;
    const days = Math.floor(hours / 24);
    return `${days}d left`;
  };

  if (loading) {
    return (
      <div className="p-4 flex items-center justify-center min-h-[400px]">
        <PixelLoader size="sm" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-center">
          <p className="text-red-400">{error}</p>
          <button
            onClick={loadProjects}
            className="mt-2 px-4 py-2 bg-red-500/20 rounded-lg text-red-400 text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!projectsData || projectsData.projects.length === 0) {
    return (
      <div className="p-5">
        <div className="rounded-2xl bg-[#1a1a1a] p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/5 flex items-center justify-center">
            <FireIconFill className="w-8 h-8 text-gray-600" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">No Active Campaigns</h3>
          <p className="text-gray-500 text-sm">
            Check back soon for UGC reward opportunities.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-full pb-32">
      {/* Success Toast */}
      {successToast && (
        <div className="fixed top-4 inset-x-4 z-50 animate-slide-down">
          <div className="relative overflow-hidden rounded-xl border border-[#f95400]/30 bg-[#f95400] shadow-lg shadow-[#f95400]/30">
            <div className="flex items-center gap-3 px-4 py-3">
              <div className="w-10 h-10 rounded-full bg-black/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-black text-lg">+{successToast.points} points!</p>
                <p className="text-black/70 text-sm">Now ranked #{successToast.rank}</p>
              </div>
              <button
                onClick={() => setSuccessToast(null)}
                className="p-1 rounded-full hover:bg-black/10 transition-colors"
              >
                <svg className="w-5 h-5 text-black/60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Welcome Header */}
      <div className="px-5 pt-5 pb-3">
        <h1 className="text-2xl font-bold text-white">UGC Rewards</h1>
      </div>

      {/* Daily Challenge Card - Multi-layer design matching Home tab */}
      <div className="px-5 mb-5">
        <div className="relative overflow-hidden rounded-2xl border border-[#f95400]/30 bg-gradient-to-br from-[#f95400]/15 via-zinc-900/50 to-black">
          {/* Grid Pattern */}
          <div className="absolute inset-0 opacity-[0.08]" style={{
            backgroundImage: `linear-gradient(#f95400 1px, transparent 1px), linear-gradient(90deg, #f95400 1px, transparent 1px)`,
            backgroundSize: '20px 20px'
          }} />
          {/* Scan Line */}
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#f95400]/[0.04] to-transparent" />

          <div className="relative z-10 p-5">
            {/* Header Row */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="glass-icon glass-icon-md glass-icon-orange">
                  <FireIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
                </div>
                <div>
                  <p className="text-sm text-[#f95400] uppercase tracking-wider">Daily Submissions</p>
                  <p className="text-xs text-white/60">UGC Rewards</p>
                </div>
              </div>
              <button
                onClick={() => {
                  hapticFeedback('medium');
                  setShowSubmitModal(true);
                }}
                disabled={projectsData.daily_submissions_remaining === 0}
                className="px-4 py-2 rounded-full flex items-center gap-2 transition-all active:scale-95 disabled:opacity-50"
                style={{
                  background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.3) 0%, rgba(255, 140, 66, 0.2) 50%, rgba(249, 84, 0, 0.25) 100%)',
                  backdropFilter: 'blur(16px)',
                  border: '1px solid rgba(249, 84, 0, 0.5)',
                  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4), 0 1px 0 rgba(255, 140, 66, 0.2) inset'
                }}
              >
                <span className="text-sm font-bold text-white">Submit</span>
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </button>
            </div>

            {/* Main Display */}
            <div className="mb-4">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-bold text-white">{projectsData.daily_submissions_remaining}</span>
                <span className="text-lg text-gray-400">/ {projectsData.daily_limit} remaining</span>
              </div>
            </div>

            {/* Progress Bar with Shine */}
            <div className="h-2.5 bg-white/10 rounded-full overflow-hidden ring-1 ring-white/10">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(projectsData.daily_submissions_remaining / projectsData.daily_limit) * 100}%`,
                  background: 'linear-gradient(90deg, #f95400 0%, #ff8c42 50%, #f95400 100%)',
                  backgroundSize: '200% 100%',
                  animation: 'progress-shine 3s ease-in-out infinite',
                  boxShadow: '0 0 12px rgba(249, 84, 0, 0.4)'
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Horizontal Scrolling Project Cards */}
      <div className="mb-5">
        <div className="flex items-center justify-between px-5 mb-3">
          <h2 className="text-lg font-semibold text-white">Active Campaigns</h2>
          <span className="text-sm text-gray-500">{projectsData.projects.length} active</span>
        </div>

        <div className="flex gap-3 overflow-x-auto pb-2 px-5 scrollbar-hide">
          {projectsData.projects.map((project) => {
            const isSelected = selectedProject?.id === project.id;
            const isEligible = projectsData.user_tweetscout_score >= project.min_tweetscout_score;

            return (
              <button
                key={project.id}
                onClick={() => {
                  hapticFeedback('light');
                  setSelectedProject(project);
                }}
                className={`relative flex-shrink-0 w-[160px] rounded-2xl p-4 text-left transition-all overflow-hidden ${
                  isSelected
                    ? 'bg-white/[0.08] backdrop-blur-xl border border-[#f95400]/50 shadow-lg shadow-[#f95400]/20'
                    : 'bg-white/[0.03] backdrop-blur-md border border-white/[0.06] hover:bg-white/[0.06] hover:border-white/10'
                }`}
              >
                {/* Grid pattern for selected */}
                {isSelected && (
                  <div className="absolute inset-0 opacity-[0.06]" style={{
                    backgroundImage: `linear-gradient(#f95400 1px, transparent 1px), linear-gradient(90deg, #f95400 1px, transparent 1px)`,
                    backgroundSize: '16px 16px'
                  }} />
                )}

                {/* Content */}
                <div className="relative z-10">
                  {/* Project Logo */}
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center overflow-hidden mb-3 ${
                    isSelected ? 'bg-[#f95400]/20 ring-1 ring-[#f95400]/30' : 'bg-white/10'
                  }`}>
                    {project.logo_url ? (
                      <img src={project.logo_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <span className={`text-lg font-bold ${isSelected ? 'text-[#f95400]' : 'text-white'}`}>
                        {project.name.charAt(0)}
                      </span>
                    )}
                  </div>

                  {/* Project Name */}
                  <h3 className="font-semibold text-sm text-white mb-1 truncate">{project.name}</h3>

                  {/* Reward */}
                  {project.reward_pool && (
                    <p className="text-xs font-medium text-[#f95400] mb-2">{project.reward_pool}</p>
                  )}

                  {/* Time + Eligibility */}
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-gray-500">{formatTimeRemaining(project.time_remaining_hours)}</span>
                    {project.min_tweetscout_score > 0 && !isEligible && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">
                        {project.min_tweetscout_score}+
                      </span>
                    )}
                  </div>
                </div>

                {/* Your rank badge */}
                {project.your_rank && (
                  <div className="absolute -top-1 -right-1 px-2 py-0.5 rounded-full bg-[#f95400] text-[10px] font-bold text-black z-20">
                    #{project.your_rank}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Leaderboard Section */}
      {selectedProject && (
        <div className="px-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Leaderboard</h2>
            <span className="text-sm text-gray-500">Top 50</span>
          </div>

          <div className="relative overflow-hidden rounded-2xl border border-[#f95400]/20 bg-gradient-to-br from-black via-zinc-900/50 to-black">
            {/* Grid Pattern */}
            <div className="absolute inset-0 opacity-[0.05]" style={{
              backgroundImage: `linear-gradient(#f95400 1px, transparent 1px), linear-gradient(90deg, #f95400 1px, transparent 1px)`,
              backgroundSize: '20px 20px'
            }} />
            {/* Scan Line */}
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#f95400]/[0.03] to-transparent" />

            <div className="relative z-10">
            {loadingLeaderboard ? (
              <div className="flex justify-center py-8">
                <PixelLoader size="xs" />
              </div>
            ) : leaderboardData?.leaderboard && leaderboardData.leaderboard.length > 0 ? (
              <div className="max-h-[400px] overflow-y-auto">
                {leaderboardData.leaderboard.slice(0, 50).map((entry, index) => {
                  const isCurrentUser = leaderboardData.user_entry?.user_id === entry.user.id;
                  const isTopThree = entry.rank <= 3;

                  return (
                    <div
                      key={entry.user.id}
                      className={`relative flex items-center gap-3 px-4 py-3 ${
                        index !== 0 ? 'border-t border-white/[0.06]' : ''
                      } ${isCurrentUser ? 'bg-[#f95400]/10' : 'hover:bg-white/[0.02]'}`}
                    >
                      {/* Grid on current user row */}
                      {isCurrentUser && (
                        <div className="absolute inset-0 opacity-[0.05]" style={{
                          backgroundImage: `linear-gradient(#f95400 1px, transparent 1px), linear-gradient(90deg, #f95400 1px, transparent 1px)`,
                          backgroundSize: '12px 12px'
                        }} />
                      )}

                      {/* Rank with Medal Badges */}
                      <div className="relative z-10 w-8 flex items-center justify-center">
                        {entry.rank === 1 ? (
                          <span className="text-xl">🥇</span>
                        ) : entry.rank === 2 ? (
                          <span className="text-xl">🥈</span>
                        ) : entry.rank === 3 ? (
                          <span className="text-xl">🥉</span>
                        ) : (
                          <span className={`text-sm font-semibold ${
                            isCurrentUser ? 'text-[#f95400]' : 'text-gray-500'
                          }`}>
                            {entry.rank}
                          </span>
                        )}
                      </div>

                      {/* Avatar */}
                      <div className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center overflow-hidden flex-shrink-0 ${
                        isCurrentUser ? 'ring-2 ring-[#f95400]' : ''
                      } bg-white/10`}>
                        {entry.user.avatar ? (
                          <img src={entry.user.avatar} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <span className="text-sm font-medium text-white">
                            {entry.user.display_name?.charAt(0) || '?'}
                          </span>
                        )}
                      </div>

                      {/* Name */}
                      <div className="relative z-10 flex-1 min-w-0">
                        <p className={`font-medium truncate ${isCurrentUser ? 'text-[#f95400]' : 'text-white'}`}>
                          {entry.user.x_username ? `@${entry.user.x_username}` : entry.user.display_name}
                          {isCurrentUser && <span className="ml-2 text-xs bg-[#f95400] text-black px-1.5 py-0.5 rounded font-bold">YOU</span>}
                        </p>
                        <p className="text-xs text-gray-500">{entry.submission_count} posts</p>
                      </div>

                      {/* Points */}
                      <span className={`relative z-10 text-sm font-bold ${isCurrentUser ? 'text-[#f95400]' : 'text-white'}`}>
                        {entry.total_points.toLocaleString()}
                      </span>
                    </div>
                  );
                })}

                {/* User's entry if not in top 50 */}
                {leaderboardData.user_entry && leaderboardData.user_entry.rank && leaderboardData.user_entry.rank > 50 && (
                  <div className="flex items-center gap-3 px-4 py-3 bg-[#f95400]/10 border-t border-[#f95400]/30">
                    <span className="w-8 text-sm font-semibold text-[#f95400]">
                      {leaderboardData.user_entry.rank}
                    </span>
                    <div className="w-10 h-10 rounded-full bg-[#f95400]/20 flex items-center justify-center ring-2 ring-[#f95400]">
                      <span className="text-sm font-bold text-[#f95400]">Y</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-[#f95400]">
                        You <span className="ml-2 text-xs bg-[#f95400] text-black px-1.5 py-0.5 rounded font-bold">YOU</span>
                      </p>
                      <p className="text-xs text-[#f95400]/60">{leaderboardData.user_entry.submission_count} posts</p>
                    </div>
                    <span className="text-sm font-bold text-[#f95400]">
                      {leaderboardData.user_entry.total_points.toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-10">
                <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-white/[0.06] backdrop-blur border border-white/[0.08] flex items-center justify-center">
                  <FireIconFill className="w-7 h-7 text-gray-600" />
                </div>
                <p className="text-gray-400 font-medium">No submissions yet</p>
                <p className="text-gray-600 text-sm mt-1">Be the first to earn points!</p>
              </div>
            )}
            </div>
          </div>
        </div>
      )}

      {/* Floating Action Button */}
      <button
        onClick={() => {
          hapticFeedback('medium');
          setShowSubmitModal(true);
        }}
        disabled={projectsData.daily_submissions_remaining === 0}
        className={`fixed bottom-24 right-4 z-40 w-14 h-14 rounded-full flex items-center justify-center transition-all ${
          projectsData.daily_submissions_remaining > 0
            ? 'glass-icon glass-icon-orange float-animation glow-pulse shadow-lg shadow-[#f95400]/20 hover:scale-105 active:scale-95'
            : 'glass-icon opacity-50 cursor-not-allowed'
        }`}
      >
        <PlusIcon className={`w-7 h-7 ${
          projectsData.daily_submissions_remaining > 0 ? 'text-[#f95400]' : 'text-gray-600'
        }`} />
      </button>

      {/* Submit Modal */}
      {showSubmitModal && (
        <LoudSubmitModal
          projects={projectsData.projects}
          projectsData={projectsData}
          preselectedProject={selectedProject}
          onClose={() => setShowSubmitModal(false)}
          onSuccess={(result) => {
            setShowSubmitModal(false);
            // Show success toast
            setSuccessToast({ points: result.points_awarded ?? 0, rank: result.new_rank ?? 0 });
            setTimeout(() => setSuccessToast(null), 4000);
            // Refresh data
            loadProjects();
            if (selectedProject) {
              loadLeaderboard(selectedProject.slug);
            }
          }}
        />
      )}
    </div>
  );
}


// Submit Modal - Premium Redesign with Project Selector
function LoudSubmitModal({
  projects,
  projectsData,
  preselectedProject,
  onClose,
  onSuccess,
}: {
  projects: LoudProject[];
  projectsData: LoudProjectsResponse;
  preselectedProject?: LoudProject | null;
  onClose: () => void;
  onSuccess: (result: LoudSubmitResponse) => void;
}) {
  const [selectedProject, setSelectedProject] = useState<LoudProject | null>(preselectedProject || null);
  const [xLink, setXLink] = useState('');
  const [urlValidation, setUrlValidation] = useState<{
    valid: boolean;
    normalized: string;
    error?: string;
  }>({ valid: false, normalized: '' });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<LoudSubmitResponse | null>(null);

  const eligibleProjects = projects.filter(p => p.can_submit);

  const handleUrlChange = (value: string) => {
    setXLink(value);
    setSubmitError(null);

    if (!value.trim()) {
      setUrlValidation({ valid: false, normalized: '' });
      return;
    }

    const result = normalizeXLink(value);
    setUrlValidation({
      valid: result.valid,
      normalized: result.normalized,
      error: result.error,
    });
  };

  const handleSubmit = async () => {
    if (!urlValidation.valid || !selectedProject) return;

    try {
      setSubmitting(true);
      setSubmitError(null);
      const result = await loudApi.submit(selectedProject.id, xLink);

      if (result.success) {
        setSubmitSuccess(result);
        hapticFeedback('success');
        setTimeout(() => {
          onSuccess(result);
        }, 2500);
      } else {
        setSubmitError(result.error || 'Submission failed');
        hapticFeedback('error');
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Submission failed');
      hapticFeedback('error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/90 backdrop-blur-md" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-lg bg-black/95 backdrop-blur-xl border-t border-x border-[#f95400]/20 rounded-t-3xl max-h-[90vh] flex flex-col animate-slide-up">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-[#f95400]/40" />
        </div>

        {/* Header */}
        <div className="px-5 pb-4 border-b border-white/10">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white">Submit Content</h2>
            <button
              onClick={onClose}
              className="p-2 rounded-full hover:bg-white/10 transition-colors"
            >
              <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {submitSuccess ? (
            /* Success State */
            <div className="text-center py-8">
              <div className="w-20 h-20 mx-auto mb-4 rounded-full gold-gradient-bg flex items-center justify-center shadow-lg shadow-[#f95400]/30">
                <svg className="w-10 h-10 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Submitted!</h3>
              <p className="text-4xl font-bold gold-gradient-text mb-1">+{submitSuccess.points_awarded}</p>
              <p className="text-gray-400">points earned</p>
              <p className="text-sm text-gray-500 mt-3">
                Now ranked <span className="text-[#f95400] font-semibold">#{submitSuccess.new_rank}</span> in {selectedProject?.name}
              </p>
            </div>
          ) : (
            <>
              {/* Step 1: Select Project */}
              <div>
                <label className="text-sm font-medium text-gray-400 mb-3 block">
                  Select Project
                </label>
                {eligibleProjects.length === 0 ? (
                  <div className="text-center py-6 bg-white/5 rounded-xl">
                    <p className="text-gray-400 text-sm">No projects available for submission</p>
                    <p className="text-gray-500 text-xs mt-1">You may have reached your limits</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {eligibleProjects.map((project) => (
                      <button
                        key={project.id}
                        onClick={() => setSelectedProject(project)}
                        className={`w-full p-3 rounded-xl border text-left transition-all flex items-center gap-3 ${
                          selectedProject?.id === project.id
                            ? 'border-[#f95400] bg-[#f95400]/10'
                            : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/[0.07]'
                        }`}
                      >
                        <div className={`w-11 h-11 rounded-xl flex items-center justify-center overflow-hidden ${
                          selectedProject?.id === project.id ? 'ring-2 ring-[#f95400]/50' : 'bg-white/10'
                        }`}>
                          {project.logo_url ? (
                            <img src={project.logo_url} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <span className="font-bold text-white">{project.name.charAt(0)}</span>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`font-medium ${selectedProject?.id === project.id ? 'text-white' : 'text-gray-200'}`}>
                            {project.name}
                          </p>
                          <p className="text-xs text-gray-500">
                            {project.max_submissions - project.user_submissions} submissions left
                          </p>
                        </div>
                        {selectedProject?.id === project.id && (
                          <div className="w-6 h-6 rounded-full gold-gradient-bg flex items-center justify-center">
                            <svg className="w-4 h-4 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Step 2: URL Input (only shown when project selected) */}
              {selectedProject && (
                <>
                  <div>
                    <label className="text-sm font-medium text-gray-400 mb-2 block">
                      X Post Link
                    </label>
                    <input
                      type="url"
                      value={xLink}
                      onChange={(e) => handleUrlChange(e.target.value)}
                      placeholder="https://x.com/username/status/..."
                      className="w-full px-4 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:border-[#f95400]/50 focus:outline-none transition-colors"
                    />
                    {urlValidation.error && (
                      <p className="mt-2 text-sm text-red-400">{urlValidation.error}</p>
                    )}
                    {urlValidation.valid && (
                      <p className="mt-2 text-xs text-green-400 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        Valid link
                      </p>
                    )}
                  </div>

                  {/* Expected Points Display */}
                  <div className="bg-[#f95400]/10 border border-[#f95400]/30 rounded-xl p-4 text-center">
                    <p className="text-sm text-gray-400 mb-1">You'll earn</p>
                    <p className="text-3xl font-bold gold-gradient-text">{projectsData.expected_points}</p>
                    <p className="text-sm text-gray-500">points</p>
                  </div>

                  {/* Error Message */}
                  {submitError && (
                    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                      <p className="text-red-400 text-sm">{submitError}</p>
                    </div>
                  )}

                  {/* Submit Button */}
                  <button
                    onClick={handleSubmit}
                    disabled={!urlValidation.valid || submitting}
                    className="w-full py-4 btn-primary text-lg flex items-center justify-center gap-2"
                  >
                    {submitting ? (
                      <>
                        <span className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                        Submitting...
                      </>
                    ) : (
                      <>
                        <FireIconFill className="w-5 h-5" style={ICON_GRADIENT_STYLE} />
                        Submit & Earn
                      </>
                    )}
                  </button>

                  {/* Limits Info */}
                  <div className="flex justify-between text-xs text-gray-500 pt-2">
                    <span>Daily: {projectsData.daily_submissions_remaining}/{projectsData.daily_limit}</span>
                    <span>{selectedProject.name}: {selectedProject.max_submissions - selectedProject.user_submissions} left</span>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
