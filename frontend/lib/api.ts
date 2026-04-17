/**
 * API client for Loudrr Mini App
 */

// Use local API proxy in production, direct backend in dev
const API_BASE_URL = typeof window !== 'undefined' && window.location.hostname !== 'localhost'
  ? '/api/miniapp'  // Use Next.js API routes (proxied to backend)
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/miniapp');

// Loud API base URL
const LOUD_API_BASE_URL = typeof window !== 'undefined' && window.location.hostname !== 'localhost'
  ? '/api/loud'  // Use Next.js API routes (proxied to backend)
  : (process.env.NEXT_PUBLIC_API_URL?.replace('/api/miniapp', '/api/loud') || 'http://localhost:8000/api/loud');

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

// Loud API request helper (same auth, different base URL)
async function loudApiRequest<T>(
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
  let url = `${LOUD_API_BASE_URL}${endpoint}`;
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
  tweetscout_last_updated?: string | null;  // ISO timestamp, null if never fetched
  // XProfile fields
  x_followers_count?: number;
  x_display_name?: string;
  // Honesty score (0-50)
  honesty_score?: number;
  // Engagement progress
  available_posts?: number;
  engaged_today?: number;
  // Whitelist status
  is_whitelisted?: boolean;
  // Feature access
  loud_access?: boolean;
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
  hours_remaining?: number;   // Hours until post expires
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
  pending_post_ids?: string[];     // IDs of posts still pending verification
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

export interface QueueClaimResponse {
  success: boolean;
  batch_id?: string;
  status?: string;
  position?: number;
  engagement_count?: number;
  message: string;
  pending_count?: number;
  remaining_seconds?: number;
  error?: string;
}

export interface ClaimBatch {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  engagement_count: number;
  passed: number | null;
  failed: number | null;
  credits_awarded: number | null;
  message: string;
  created_at: string;
  completed_at: string | null;
}

export interface ClaimHistoryResponse {
  batches: ClaimBatch[];
  pending_engagements: number;
  has_processing: boolean;
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

// Waitlist registration types
export interface OtherPlatformEntry {
  platform: 'youtube' | 'tiktok' | 'other';
  username: string;
  platform_name?: string;
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

  /**
   * Queue verification for async processing (instant response)
   * Like spot trading - queues and returns immediately
   */
  queueClaim: () =>
    apiRequest<QueueClaimResponse>('/session/queue-claim/', {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /**
   * Get claim/verification history
   * Returns recent batches with status and results
   */
  getClaimHistory: () =>
    apiRequest<ClaimHistoryResponse>('/claims/history/'),

  /**
   * Complete onboarding - fetches TweetScout and activates user
   * Called when user clicks "Let's Go Loudrr" button
   */
  completeOnboarding: () =>
    apiRequest<{
      success: boolean;
      tweetscout_score: number;
      tier: string;
      followers_count?: number;
      display_name?: string;
      already_onboarded?: boolean;
      message?: string;
    }>('/onboarding/complete/', {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /**
   * Register interest in a coming feature
   */
  registerFeatureInterest: (feature: string, interests: string[]) =>
    apiRequest<{ success: boolean }>('/feature-interest/', {
      method: 'POST',
      body: JSON.stringify({ feature, interests }),
    }),

  /**
   * Check if user has registered interest in a feature
   */
  getFeatureInterest: (feature: string) =>
    apiRequest<{ registered: boolean }>(`/feature-interest/?feature=${feature}`),

  // =============================================================================
  // WAITLIST - In-App Registration
  // =============================================================================

  /**
   * Check waitlist status for current Telegram user
   * Returns: "approved" | "waitlisted" | "not_registered"
   */
  checkWaitlistStatus: () =>
    apiRequest<{
      status: 'approved' | 'waitlisted' | 'not_registered';
      x_username?: string;
      submitted_at?: string;
      referral_code?: string;
    }>('/waitlist/status/'),

  /**
   * Register for waitlist directly from mini app
   * Requires email + X profile link, optional referral_code
   * Sends waitlist card to user via Telegram on success
   */
  registerWaitlist: (
    email: string, x_link: string, referral_code?: string,
    region?: string, niche?: string, other_platforms?: OtherPlatformEntry[]
  ) =>
    apiRequest<{
      status: 'registered' | 'already_registered';
      message: string;
      referral_code?: string;
    }>('/waitlist/register/', {
      method: 'POST',
      body: JSON.stringify({
        email, x_link,
        ...(referral_code && { referral_code }),
        ...(region && { region }),
        ...(niche && { niche }),
        ...(other_platforms?.length && { other_platforms }),
      }),
    }),
};

// =============================================================================
// LOUD API - UGC Rewards Feature
// =============================================================================

export interface LoudProject {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  description: string;
  ends_at: string;
  time_remaining_hours: number;
  reward_pool: string;
  min_tweetscout_score: number;
  max_submissions: number;
  user_submissions: number;
  can_submit: boolean;
  cannot_submit_reason: string | null;
  total_participants: number;
  your_rank: number | null;
  your_points: number;
}

export interface LoudProjectsResponse {
  projects: LoudProject[];
  daily_submissions_remaining: number;
  daily_limit: number;
  expected_points: number;
  user_tweetscout_score: number;
}

export interface LoudSubmitResponse {
  success: boolean;
  submission_id?: string;
  points_awarded?: number;
  new_total_points?: number;
  new_rank?: number;
  daily_submissions_remaining?: number;
  project_submissions_remaining?: number;
  error?: string;
}

export interface LoudLeaderboardUser {
  id: string;
  display_name: string;
  x_username: string | null;
  avatar: string | null;
}

export interface LoudLeaderboardEntry {
  rank: number;
  user: LoudLeaderboardUser;
  total_points: number;
  submission_count: number;
}

export interface LoudUserEntry {
  user_id?: string;
  rank: number | null;
  total_points: number;
  submission_count: number;
}

export interface LoudLeaderboardResponse {
  project: {
    name: string;
    slug: string;
    ends_at: string;
    reward_pool: string;
  };
  leaderboard: LoudLeaderboardEntry[];
  user_entry: LoudUserEntry | null;
  total_participants: number;
}

// Loud API Functions
export const loudApi = {
  /**
   * Get live projects with user's submission counts and eligibility
   */
  getProjects: () => loudApiRequest<LoudProjectsResponse>('/projects/'),

  /**
   * Submit content to a project
   * @param projectId - The project UUID
   * @param xLink - The X/Twitter post URL
   */
  submit: (projectId: string, xLink: string) =>
    loudApiRequest<LoudSubmitResponse>('/submit/', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, x_link: xLink }),
    }),

  /**
   * Get project leaderboard
   * @param projectSlug - The project slug
   */
  getLeaderboard: (projectSlug: string) =>
    loudApiRequest<LoudLeaderboardResponse>(`/leaderboard/${projectSlug}/`),
};

// URL normalization helper for frontend validation
export function normalizeXLink(url: string): {
  valid: boolean;
  normalized: string;
  tweetId: string;
  username: string;
  error?: string;
} {
  // Strip protocol
  let clean = url.replace(/^https?:\/\//, '');

  // Reject i/status (anonymous links)
  if (clean.includes('/i/status/')) {
    return {
      valid: false,
      normalized: '',
      tweetId: '',
      username: '',
      error: 'Anonymous links not accepted. Use link with username.',
    };
  }

  // Extract username and tweet ID
  const match = clean.match(/(?:x\.com|twitter\.com)\/([^\/]+)\/status\/(\d+)/);
  if (!match) {
    return {
      valid: false,
      normalized: '',
      tweetId: '',
      username: '',
      error: 'Invalid link format. Use: x.com/username/status/...',
    };
  }

  const [, username, tweetId] = match;

  // Reject if username is 'i' or 'intent'
  if (['i', 'intent', 'share', 'search'].includes(username.toLowerCase())) {
    return {
      valid: false,
      normalized: '',
      tweetId: '',
      username: '',
      error: 'Invalid link format',
    };
  }

  // Build normalized URL (no query params)
  const normalized = `https://x.com/${username}/status/${tweetId}`;

  return { valid: true, normalized, tweetId, username };
}
