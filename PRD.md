# ECHO - Product Requirements Document (PRD)

**Version:** 1.0 (Launch Version)
**Last Updated:** January 2026
**Product Name:** ECHO (Engagement Credit Hub & Optimization)

---

## 1. Executive Summary

ECHO is a **Telegram Mini App-first** engagement platform designed for creators and projects on X (Twitter).

It enables users to:
- **Earn karma (credits)** by engaging with posts (like + reply)
- **Spend karma** to receive engagement on their own posts
- **Participate** in sponsored engagement and reward campaigns
- **Optionally use intent-based tools** to speed up engagement safely

ECHO monetizes through:
1. **Monthly retainers** (sponsored engagement)
2. **One-off campaigns** (reward-based)
3. **Pro subscriptions** (intent + AI assist)

The system is designed to:
- Scale with reply-heavy users ("reply guys")
- Avoid X bans or shadowbans
- Prevent credit inflation
- Generate predictable revenue

---

## 2. Core Design Principles

### 1. Human-first behaviour
- No auto-posting
- No forced automation
- Users always confirm actions

### 2. Credits ≠ Money
- Karma is internal utility
- Cannot be cashed out
- Rewards are separate

### 3. Friction is a feature
- Small friction keeps users safe
- Intent tools are optional, capped

### 4. Asymmetry is healthy
- Some users grind more
- Some post more
- System balances globally, not per user

---

## 3. Core User Roles

### Users
- Engage with posts
- Earn karma
- Submit posts for engagement
- Optional Pro features

### Sponsors / Projects
- Pay monthly retainers
- Run one-off campaigns
- Receive guaranteed engagement

### Admins
- Moderate posts
- Inject sponsored posts
- Manage campaigns
- Handle payouts manually (V1)

---

## 4. Karma (Credits) System

### 4.1 What is Karma?
- Non-transferable internal credits
- Earned by verified engagement
- Spent to receive engagement or enter raffles
- Subject to decay if inactive

### 4.2 Earning Karma

| Action | Karma |
|--------|-------|
| Like + Reply (verified) | +1 |
| Daily earning cap | 160 |

**Engagement rules:**
- User must like AND reply
- Both actions verified via API
- Minimum time between actions enforced

### 4.3 Spending Karma

| Action | Karma Cost |
|--------|------------|
| Submit post | 80 |
| Raffle entry | 10 |

Karma spent is either:
- Locked in escrow
- Or permanently burned

---

## 5. Engagement Flow (Standard)

1. User opens **Engage tab**
2. Sees a post (organic or sponsored)
3. Clicks **Open Post**
4. Likes post manually
5. Replies manually or via intent
6. Returns to ECHO
7. Clicks **I liked & replied**
8. Backend verifies
9. Karma awarded

---

## 6. Intent System (Safety-Critical)

### 6.1 Intent Toggles (Top of Engage Tab)

**Toggle 1: Quick Like**
- Default: ON
- Uses: `https://twitter.com/intent/like?tweet_id=ID`
- Unlimited but rate-limited

**Toggle 2: Quick Reply**
- Default: OFF
- Pro-only
- Uses: `https://twitter.com/intent/tweet?in_reply_to=ID`

**Toggle 3: AI Reply Assist**
- Default: OFF
- Pro-only
- Optional per reply

### 6.2 Intent Limits (Hard Rules)

| Feature | Free | Pro |
|---------|------|-----|
| Like intent | Yes | Yes |
| Reply intent | No | 20-30/day |
| AI assist | No | 10-15/day |
| Auto-post | No | No |

Intent reply auto-disables after cap.

### 6.3 AI Assist Rules
- Never auto-post
- Always editable
- Uses templates + cached AI (no per-reply AI)
- Warn users to use sparingly

---

## 7. Feed Ordering & Quality Protection

### Tier-Based Weighting

Posts are ranked using:
```
feed_score =
  (author_tier × 0.5)
+ (freshness × 0.3)
+ (engagement_remaining × 0.2)
```

This ensures:
- High-tier users see higher-quality posts
- Low-tier users mostly engage among themselves
- Sponsored posts injected with caps

---

## 8. Post Submission & Escrow

1. User submits post
2. 80 karma locked
3. Each verified engagement releases 1 karma
4. Post completes at 80 engagements or expires
5. Expired posts refund unused karma partially

---

## 9. Sponsored Retainer Model (Primary Revenue)

### 9.1 What Sponsors Get
- Monthly fee ($300-$500)
- All posts injected into feed
- Ongoing engagement

### 9.2 Sponsored Post Rules
- Tagged "Sponsored"
- Same karma reward (1)
- Max 10 sponsored posts/day (at ~100 users)
- Frequency capped in feed

### 9.3 Expected Delivery (Sell This)
- 40-60 real comments per post
- Delivered over 24-72 hours
- Likes included

---

## 10. Campaigns (Secondary Revenue)

### 10.1 Campaign Types

**A. Raffle Campaign**
- Fixed pool (e.g. $2,000)
- Open for X days
- Winners selected randomly

**B. Score-Based Campaign**
- Eligibility via TweetScout / Kaito
- Weighted payouts
- Ends when pool exhausted

### 10.2 Campaign Participation
- Users submit tweet link
- Verified via API
- Manual payouts in V1

---

## 11. Pro Subscription

**Price:** $10/month

**Unlocks:**
- Reply intent toggle
- AI reply assist
- Higher visibility (future)
- Analytics (future)

**Pro does NOT:**
- Increase karma rate
- Allow automation
- Remove limits

---

## 12. Karma Decay & Streaks

### 12.1 Inactivity Decay
- After 14 days inactive
- 1-2% decay/day
- Pauses immediately on activity

### 12.2 Streak System
- 1+ engagement/day = streak continues
- No spending required

**Milestones:**
| Days | Bonus |
|------|-------|
| 7 days | +5 karma |
| 14 days | +6 karma |
| 30 days | +10 karma |

Streak rewards are decay-proof.

---

## 13. Anti-Abuse & Verification

### Verification
- Likes + replies verified via **twitterapi.io**
- Random audits for engagement
- Full verification for campaigns

### Protection
- Rate limits
- Duplicate reply detection
- Minimum reply length
- Manual moderation tools

---

## 14. Database Schema (Simplified)

### User
```
id
telegram_id
username
tier
karma
wallet_address
is_pro
last_active_at
```

### Post
```
id
user_id
tweet_id
is_sponsored
escrow_total
escrow_remaining
status
```

### Engagement
```
id
user_id
post_id
verified
created_at
```

### Campaign
```
id
type
budget
status
```

---

## 15. API Endpoints (High-Level)

```
POST /engagement/start
POST /engagement/verify
POST /post/submit
GET  /feed
POST /intent/usage
GET  /campaigns
POST /campaigns/join
```

---

## 16. Infrastructure (V1)

- Django + DRF
- PostgreSQL (Supabase)
- Telegram Mini App (Next.js)
- Single VPS (no Kubernetes)
- Manual payouts
- Background jobs for verification

---

## 17. Launch Scope (3-Day MVP)

### Included
- Karma loop
- Sponsored posts
- Intent toggles
- Pro subscription
- Manual ops

### Excluded
- Automated payouts
- Web2 expansion
- Smart contracts
- Advanced analytics

---

## 18. Success Metrics

- DAU / WAU
- Karma earned vs burned
- Sponsored post delivery
- Pro conversion rate
- Retention of high-tier users

---

## 19. Final Product Summary

**ECHO is:**
- A coordination layer for engagement
- A retainer-based growth engine for brands
- A safe productivity tool for reply guys
- A scalable, monetisable system

**No automation abuse.**
**No fake engagement.**
**No overengineering.**

**Just controlled scale.**

---

## 20. Current Implementation Status

### What's Built
| Feature | Status |
|---------|--------|
| Django backend | Done |
| PostgreSQL (Supabase) | Done |
| Telegram Mini App (Next.js) | Done |
| Basic karma system | Done |
| Home/Engage/Submit/Stats tabs | Done |
| Click tracking (Layer 1) | Done |

### What Needs Building (Priority Order)

| Feature | Priority | Notes |
|---------|----------|-------|
| Like + Reply verification via twitterapi.io | HIGH | Core to v1 |
| Intent toggles (Quick Like, Quick Reply) | HIGH | Safety-critical |
| Sponsored post injection | HIGH | Revenue |
| Pro subscription ($10/mo) | HIGH | Revenue |
| Feed scoring algorithm | MEDIUM | Quality control |
| Campaigns system | MEDIUM | Secondary revenue |
| AI Reply Assist | MEDIUM | Pro feature |
| Karma decay system | LOW | Can add post-launch |
| Wallet address field | LOW | For future payouts |

### Schema Updates Needed
- Add `wallet_address` to User
- Add `is_sponsored` to Post
- Add `tweet_id` to Post (extract from URL)
- Add `verified` boolean to Engagement
- Create Campaign model

---

## 21. Quick Start (Development)

```bash
# Terminal 1: Backend
cd backend && python manage.py runserver 0.0.0.0:8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Tunnel (for Telegram)
ngrok http 3000
```

**URLs:**
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| Admin | http://localhost:8000/admin |
| Health Check | http://localhost:8000/api/miniapp/health/ |
