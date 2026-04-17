# Loudrr User Flows

Complete documentation of every user flow, traced from actual code.

**Last Updated**: February 20, 2026

---

## Auth State Machine

The mini app uses a single `authState` to decide which screen to render:

```
loading -> not_in_telegram  (no Telegram initData)
loading -> approved         (User record exists in DB)
loading -> waitlisted       (WaitlistEntry exists, no User)
loading -> not_registered   (neither exists)
```

| authState | Screen | Condition |
|-----------|--------|-----------|
| `not_in_telegram` | "Open in Telegram" link | No Telegram Web App `initData` |
| `not_registered` | `WaitlistRegistrationScreen` | No User, no WaitlistEntry |
| `waitlisted` | `WaitlistPendingScreen` | WaitlistEntry exists (SUBMITTED status) |
| `approved` | Main app (tabs) | User record exists |
| `approved` + no tweetscout | `OnboardingScreen` | Legacy fallback, rare |

**Code**: [frontend/app/page.tsx](../frontend/app/page.tsx) `loadInitialData()` (lines 198-261)

---

## Flow 1: New User from Website

```
loudrr.com -> Click "Join on Telegram" -> t.me/loudrr_bot -> Telegram opens bot
```

The landing page has a single CTA button linking to `https://t.me/loudrr_bot`. No email form, no API calls. User goes directly to the Telegram bot.

**Code**: [frontend/app/page.tsx](../frontend/app/page.tsx) (line ~226-252)

---

## Flow 2: Bot /start (New User)

```
User sends /start (or opens t.me/loudrr_bot)
    -> Bot checks: User.objects.get(telegram_id=...) -> DoesNotExist
    -> Bot sends welcome message + "Open Loudrr" inline button
    -> Button opens mini app via WebAppInfo(url=miniapp_url)
```

**Message sent**:
> Welcome to Loudrr, {first_name}!
>
> Engage with posts on X, earn karma, and grow your reach.
>
> Tap below to get started:
>
> [Open Loudrr] (WebApp button)

**Code**: [backend/bots/telegram/handlers.py](../backend/bots/telegram/handlers.py) `start_handler` (lines 18-66)

---

## Flow 3: Bot /start (Returning Approved User)

```
User sends /start
    -> Bot checks: User.objects.get(telegram_id=...) -> Found
    -> Bot sends "Welcome back" message with karma/streak stats
    -> "Open Loudrr" inline button
```

**Message sent**:
> Welcome back, {first_name}!
>
> Karma: {credits}
> Streak: {streak} days
>
> Tap below to start engaging!
>
> [Open Loudrr] (WebApp button)

---

## Flow 4: Bot /start with Referral (ref_ deep link)

```
User clicks: t.me/loudrr_bot?start=ref_ABC123
    -> Bot extracts ref_code = "ABC123"
    -> If user EXISTS: referral code IGNORED, normal welcome back
    -> If user DOES NOT EXIST:
        -> app_url = "{miniapp_url}?ref=ABC123"
        -> "Open Loudrr" button opens mini app with ?ref=ABC123 in URL
        -> WaitlistRegistrationScreen reads ?ref= from window.location.search
        -> Code auto-captured, sent with registration API call
```

The referral code flows: bot URL param -> WebApp URL query string -> frontend `useEffect` -> API request body -> stored on WaitlistEntry.

**Code**: [handlers.py](../backend/bots/telegram/handlers.py) (line 26-30), [page.tsx](../frontend/app/page.tsx) WaitlistRegistrationScreen (lines 3356-3365)

---

## Flow 5: Mini App Opens (Auth Detection)

```
Mini app loads
    -> initTelegramWebApp()
    -> loadInitialData():
        1. Check Telegram initData exists
           -> No: authState = 'not_in_telegram' (STOP)

        2. Try api.getUser() + api.getSettings() in parallel
           -> Success: authState = 'approved' (STOP)

        3. getUser() failed (401) -> try api.checkWaitlistStatus()
           -> "approved": retry getUser(), authState = 'approved'
           -> "waitlisted": authState = 'waitlisted'
           -> "not_registered": authState = 'not_registered'
           -> API error: fallback to 'not_registered'
```

**Backend auth**: `X-Telegram-Init-Data` header validated via HMAC against bot token. `telegram_id` extracted from parsed user data. User looked up by `telegram_id`.

**Code**: [page.tsx](../frontend/app/page.tsx) `loadInitialData()` (lines 198-261)

---

## Flow 6: Registration (not_registered -> waitlisted)

```
WaitlistRegistrationScreen shows:
    - Email input
    - X Profile link input (https://x.com/username)
    - "Join Waitlist" button
    - Referral code auto-captured from ?ref= URL param (hidden)

User submits form:
    -> POST /api/miniapp/waitlist/register/
       Body: { email, x_link, referral_code? }

Backend WaitlistRegisterView:
    1. Validate Telegram init data (HMAC)
    2. Validate email (Django EmailValidator)
    3. Extract x_username from x_link via extract_username_from_profile_url()
    4. Check existing registration (telegram_id) -> return "already_registered" if found
    5. Check conflicts (email taken, x_username taken)
    6. Validate referral_code:
       -> Check User.objects.filter(referral_code=code) -> set referrer
       -> If not in Users, check WaitlistEntry.objects.filter(referral_code=code)
       -> Invalid codes silently ignored
    7. Create WaitlistEntry (status=SUBMITTED directly, no PENDING)
       -> referral_code auto-generated on save (8-char uppercase, unique)
    8. Signal fires -> OutboxEvent WAITLIST_SUBMITTED created
    9. Celery processes outbox -> Telegram bot sends waitlist card photo to user

Response: { status: "registered", x_username, referral_code }

Frontend:
    -> hapticFeedback('success')
    -> setWaitlistData({ x_username, referral_code })
    -> setAuthState('waitlisted')
    -> WaitlistPendingScreen renders
```

**Code**: [views.py](../backend/miniapp/views.py) WaitlistRegisterView (lines 1387-1519), [signals.py](../backend/core/signals.py) (lines 122-170)

---

## Flow 7: Waitlist Pending Screen (waitlisted)

```
WaitlistPendingScreen shows:
    - Logo
    - "You're on the Waitlist"
    - "We'll notify you on Telegram when your account is approved."
    - @username badge
    - Card image from: loudrr.com/api/cards/waitlist?username={xUsername}
    - Three share buttons:
        [Copy]  - Copies: "I just joined the @loudrrHQ waitlist!\n\nJoin me ...\nt.me/loudrr_bot?start=ref_{referralCode}"
        [Post]  - Opens: x.com/intent/tweet?text=...&url=loudrr.com/waitlist/{xUsername}
        [Share] - Opens: t.me/share/url?url=t.me/loudrr_bot?start=ref_{referralCode}&text=...
    - "Thank you for your patience. High-quality accounts are prioritized."
```

The share page at `loudrr.com/waitlist/{username}` has OG meta tags so X renders a card preview image when the link is shared.

**Data sources**:
- `xUsername`: from registration response or checkWaitlistStatus response
- `referralCode`: from WaitlistEntry.referral_code (auto-generated)

**Code**: [page.tsx](../frontend/app/page.tsx) WaitlistPendingScreen (lines 3510-3645)

---

## Flow 8: Admin Approves Waitlist Entry

```
Django Admin -> Select WaitlistEntry -> Action: "Approve selected entries"

For each entry (inside transaction.atomic):
    1. Validate: telegram_id exists, x_username exists, no duplicate User
    2. Create User:
        - telegram_id, telegram_username, display_name from entry
        - x_username from entry
        - is_whitelisted = True
        - tweetscout_score = 0
        - tweetscout_last_updated = now() (prevents OnboardingScreen from showing)
    3. Update entry:
        - status = APPROVED
        - approved_at = now()
        - created_user = user (OneToOne link)

Signals fire on entry.save():
    Signal 1 (pre_save): Store _previous_status = SUBMITTED
    Signal 2 (post_save - approval notification):
        -> OutboxService.queue_waitlist_approved()
        -> Celery: send_approval_notification(entry)
        -> Bot sends approval card photo + "Open Loudrr" WebApp button
    Signal 3 (post_save - referral increment):
        -> If entry.referrer exists:
        -> ReferralService.increment_referral_count()
        -> Referrer's total_referrals += 1 (F() + select_for_update)

After transaction:
    4. OutboxService.queue_tweetscout_fetch(user.id)
       -> Celery: Fetches TweetScout data, creates XProfile, updates user score

Telegram notification sent to user:
    Photo: Approval card image
    Caption: "Welcome to Loudrr! You've been approved! Tap below to start."
    Button: [Open Loudrr] (WebApp)
```

**Code**: [admin.py](../backend/core/admin.py) `approve_entries` (lines 679-745), [signals.py](../backend/core/signals.py), [notifications.py](../backend/bots/telegram/notifications.py)

---

## Flow 9: Approved User Opens App (First Time)

```
Mini app loads -> loadInitialData()
    -> api.getUser() SUCCEEDS (User was created by admin approval)
    -> authState = 'approved'

Rendering check:
    user.is_whitelisted = true
    user.tweetscout_last_updated = set (admin sets it to now() on creation)
    -> OnboardingScreen condition is FALSE
    -> User goes directly to main app

Main app renders with tabs: Home, Engage, Campaigns, Earn, Loud
```

---

## Flow 10: Admin Rejects Waitlist Entry

```
Django Admin -> Select WaitlistEntry -> Action: "Reject selected entries"

For each entry:
    -> entry.status = REJECTED
    -> entry.save()

No User is created. No notification is sent.
User re-opens mini app:
    -> api.getUser() fails (401)
    -> api.checkWaitlistStatus() returns... (depends on how status view handles REJECTED)
```

**Note**: The `WaitlistStatusView` does not distinguish between SUBMITTED and REJECTED. If a WaitlistEntry exists (regardless of status), it returns `"waitlisted"`. A rejected user would still see the WaitlistPendingScreen.

**Code**: [admin.py](../backend/core/admin.py) `reject_entries` (lines 748-753)

---

## Referral Code Flow (Complete)

```
User A registers -> WaitlistEntry created with auto-generated referral_code "XYZ789"
User A sees WaitlistPendingScreen -> shares link: t.me/loudrr_bot?start=ref_XYZ789

User B clicks link -> Bot sends /start ref_XYZ789
    -> Bot sets app_url = "{miniapp_url}?ref=XYZ789"
    -> User B opens mini app with ?ref=XYZ789 in URL

User B registers:
    -> referral_code "XYZ789" sent to backend
    -> Backend checks User table: no match
    -> Backend checks WaitlistEntry table: found User A's entry!
    -> referral_code_valid = True
    -> referrer = None (User A isn't a User yet, just a WaitlistEntry)
    -> Entry created with referral_code_used = "XYZ789"

Later, admin approves User A:
    -> User A becomes a User
    -> But User B's entry.referrer was set to None, so no increment happens

KEY LIMITATION: Waitlist-to-waitlist referrals are TRACKED (referral_code_used stored)
but NOT COUNTED (total_referrals not incremented because referrer FK requires a User).
Only referrals from approved Users -> new entries get counted on approval.
```

---

## Telegram Notifications Sent

| Event | Trigger | Message | Image |
|-------|---------|---------|-------|
| Waitlist confirmation | WaitlistEntry created (SUBMITTED) | "You're on the Loudrr waitlist! X: @username. We'll notify you here when you get access." | Waitlist card |
| Approval notification | Admin approves entry | "Welcome to Loudrr! You've been approved! Tap below to start." + [Open Loudrr] button | Approval card |

Both cards generated via `bots/telegram/image_utils.py` which calls `loudrr.com/api/cards/{waitlist,approval}?username=...`

**Code**: [notifications.py](../backend/bots/telegram/notifications.py), [image_utils.py](../backend/bots/telegram/image_utils.py)

---

## Key Files

| File | Purpose |
|------|---------|
| [frontend/app/page.tsx](../frontend/app/page.tsx) | Landing page ("Join on Telegram" button) |
| [backend/bots/telegram/handlers.py](../backend/bots/telegram/handlers.py) | Bot /start handler, referral extraction |
| [frontend/app/app/page.tsx](../frontend/app/app/page.tsx) | Mini app auth state machine, all screens |
| [frontend/lib/api.ts](../frontend/lib/api.ts) | API client (getUser, checkWaitlistStatus, registerWaitlist) |
| [backend/miniapp/views.py](../backend/miniapp/views.py) | WaitlistRegisterView, WaitlistStatusView, UserInfoView |
| [backend/core/signals.py](../backend/core/signals.py) | Outbox events on WaitlistEntry status changes |
| [backend/core/admin.py](../backend/core/admin.py) | Approve/reject admin actions |
| [backend/bots/telegram/notifications.py](../backend/bots/telegram/notifications.py) | Telegram card + message sending |
| [backend/core/services/outbox.py](../backend/core/services/outbox.py) | Outbox event processing and routing |
