/**
 * API client for Loudrr Mini App
 */

// Use local API proxy in production, direct backend in dev
const API_BASE_URL = typeof window !== 'undefined' && window.location.hostname !== 'localhost'
  ? '/api/miniapp'  // Use Next.js API routes (proxied to backend)
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/miniapp');

// Debug telegram ID for local testing (only used when not in Telegram)
const DEBUG_TELEGRAM_ID = process.env.NEXT_PUBLIC_DEBUG_TELEGRAM_ID || '6451704338';

// Get Telegram Web App init data
function getTelegramInitData(): string {
  if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp) {
    return (window as any).Telegram.WebApp.initData;
  }
  return '';
}

// Check if running inside Telegram
function isInTelegram(): boolean {
  return typeof window !== 'undefined' && !!(window as any).Telegram?.WebApp?.initData;
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

  // Add debug telegram_id for local testing when not in Telegram
  let url = `${API_BASE_URL}${endpoint}`;
  if (!isInTelegram() && DEBUG_TELEGRAM_ID) {
    const separator = endpoint.includes('?') ? '&' : '?';
    url = `${url}${separator}telegram_id=${DEBUG_TELEGRAM_ID}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || error.message || 'Request failed');
  }

  return response.json();
}

// Types
export interface User {
  id: string;
  display_name: string;
  telegram_username: string;
  credits: number;
  daily_earned: number;
  daily_cap: number;
  total_engagements: number;
  tier: string;
  current_streak: number;
  // v1 fields
  is_pro?: boolean;
  x_username?: string;
  tweetscout_score?: number;
  // XProfile fields
  x_followers_count?: number;
  x_display_name?: string;
  // Honesty score (0-50)
  honesty_score?: number;
  // Engagement progress
  available_posts?: number;
  engaged_today?: number;
}

export interface Post {
  id: string;
  x_link: string;
  redirect_url: string;
  creator: string;
  creator_x_username?: string;
  creator_avatar?: string;  // X profile avatar URL
  escrow_remaining: number;
  engagement_progress: number;
  // v1 fields
  is_sponsored?: boolean;
  tweet_id?: string;
  created_at?: string;  // ISO date string
  // Cached tweet content for feed display
  tweet_text?: string;
  tweet_author_name?: string;
  tweet_author_username?: string;
  tweet_author_avatar?: string;
  tweet_media?: string[];
  tweet_created_at?: string;  // ISO date string
}

export interface SessionResponse {
  posts: Post[];
  pending_count: number;           // User's unverified engagement count (persists across sessions)
  pending_post_ids: string[];      // Post IDs with pending engagements
  show_verification: boolean;      // True if user has 10+ pending engagements
  user?: {
    credits: number;
    daily_earned: number;
    daily_cap: number;
  };
  message?: string;
  // Legacy fields (kept for backward compatibility)
  session_token?: string | null;
  clicked_posts?: string[];
  expires_at?: string;
  resumed?: boolean;
}

export interface ClickResponse {
  success: boolean;
  engagement_id: string;
  created: boolean;               // True if new engagement created
  pending_count: number;          // Updated pending count
  show_verification: boolean;     // True if user now has 10+ pending
}

export interface CompleteResponse {
  success: boolean;
  message: string;
  credits_awarded: number;
  new_balance?: number;
  daily_earned?: number;
  pending_count?: number;          // Remaining pending (failed verifications)
  verification_results?: Array<{
    post_id: string;
    passed: boolean;
  }>;
  // New simplified response fields
  passed?: number;                 // Number of passed verifications
  failed?: number;                 // Number of failed verifications (need re-engagement)
  total_verified?: number;         // Total verified (same as passed)
  honesty_score?: number;          // User's honesty score (0-50)
  // Legacy fields (for backwards compatibility)
  passes?: number;
  verification_ratio?: number;
  penalty_applied?: number;
  warning?: boolean;
  retry_required?: boolean;
  failures?: number;
}

export interface SubmitPostResponse {
  success: boolean;
  message: string;
  post_id?: string;
  new_balance?: number;
  escrow?: number;
  error?: string;
}

export interface AppSettings {
  post_cost_min: number;
  post_cost_max: number;
}

export interface UserStats {
  user: {
    display_name: string;
    telegram_username: string;
    credits: number;
    tier: string;
    current_streak: number;
    total_credits_earned: number;
    total_credits_spent: number;
  };
  posts: {
    total: number;
    active: number;
    completed: number;
  };
  engagements: {
    given: number;
    received: number;
  };
  recent_posts: Array<{
    id: string;
    x_link: string;
    status: string;
    escrow_remaining: number;
    engagement_progress: number;
    created_at: string;
  }>;
}

// API Functions
export const api = {
  /**
   * Get app settings (post cost min/max, etc.)
   * Cached on backend, fetched once on frontend load
   */
  getSettings: () => apiRequest<AppSettings>('/settings/'),

  /**
   * Get current user info
   */
  getUser: () => apiRequest<User>('/user/'),

  /**
   * Start engagement flow - returns posts and user's pending progress
   * Progress persists indefinitely (no session expiry)
   */
  startSession: () => apiRequest<SessionResponse>('/session/start/', { method: 'POST' }),

  /**
   * Record a click/engagement on a post
   * Creates Engagement with verified=False (pending verification)
   * No session token needed - tracks at user level
   */
  recordClick: (postId: string) =>
    apiRequest<ClickResponse>('/session/click/', {
      method: 'POST',
      body: JSON.stringify({ post_id: postId }),
    }),

  /**
   * Verify user returned after clicking a link (optional)
   */
  verifyReturn: (postId: string) =>
    apiRequest<{ success: boolean; verified: boolean; engagement_id?: string }>('/session/verify-return/', {
      method: 'POST',
      body: JSON.stringify({ post_id: postId }),
    }),

  /**
   * Verify pending engagements and claim credits
   * Verifies user's unverified Engagements (no session token needed)
   */
  completeSession: () =>
    apiRequest<CompleteResponse>('/session/complete/', {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /**
   * Submit a new X post
   * @param xLink - The X/Twitter post URL
   * @param karmaAmount - Amount of karma to spend (between min and max from settings)
   */
  submitPost: (xLink: string, karmaAmount: number) =>
    apiRequest<SubmitPostResponse>('/post/submit/', {
      method: 'POST',
      body: JSON.stringify({ x_link: xLink, karma_amount: karmaAmount }),
    }),

  /**
   * Get detailed user stats
   */
  getUserStats: () => apiRequest<UserStats>('/user/stats/'),

  /**
   * Link X/Twitter account
   * Returns XProfile data including TweetScout score and tier
   */
  linkXAccount: (xUsername: string) =>
    apiRequest<{
      success: boolean;
      x_username: string;
      tweetscout_score: number;
      tier: string;
      followers_count: number;
      display_name: string;
    }>(
      '/user/link-x/',
      {
        method: 'POST',
        body: JSON.stringify({ x_username: xUsername }),
      }
    ),
};
