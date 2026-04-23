# How the Card System Works (For Beginners)

> **Audience:** You're new to development. This doc explains every concept from the ground up, in plain English, before showing the code.
>
> **Goal:** By the end you understand exactly what happens when a user submits the waitlist or gets approved, and how a pretty card image ends up in their Telegram chat.
>
> **Time to read:** ~30 minutes if you stop and look at each code file mentioned.

---

## Part 1 — The big idea (in 3 sentences)

1. Loudrr sends users a **picture** in Telegram when they sign up or get approved.
2. That picture is generated **on demand** by visiting a URL — like how a Google Maps screenshot is generated when you click a link.
3. There are **two completely separate programs** doing this work: one builds the picture, the other figures out when to send it.

If you understand that, the rest is just details.

---

## Part 2 — Why TWO programs and not one?

We have:
- **Frontend** (Next.js) — the website. Lives in `frontend/`
- **Backend** (Django) — the server. Lives in `backend/`

You might ask: *why don't we just have Django build the picture too?*

**Answer:** because building a pretty picture from JSX (React-like code) is what Next.js is REALLY good at, and Django is bad at. So we use the right tool for the job.

The two programs talk to each other over **HTTP** (the same protocol your browser uses). When Django needs a picture, it visits a URL on Next.js, just like your browser would. Next.js sends back the picture bytes. Django then forwards those bytes to Telegram.

This pattern is called "service-oriented architecture" — different services doing different jobs.

---

## Part 3 — Concept primer (terms you'll see)

If any of these are confusing, this section explains them in plain English.

### What is an "endpoint" / "route"?
A URL that responds to a request. Like `https://loudrr.com/health/` is an endpoint — when you visit it, the server runs some code and returns something.

### What is "GET" vs "POST"?
Two different ways to make a request:
- **GET** = "give me this thing" (reading data, like loading a page)
- **POST** = "I'm sending you data, do something with it" (form submissions, creating things)

When you type a URL in your browser bar and hit enter, you're doing a GET. When you click "Submit" on a form, you usually trigger a POST.

### What is JSX?
A way to write HTML inside JavaScript. Looks like:
```jsx
<div style={{ color: 'red' }}>Hello</div>
```
React invented it. Next.js uses it. Inside `frontend/app/api/cards/waitlist/route.tsx`, we write JSX, and a library called Satori turns it into a PNG image.

### What is an "Edge function"?
Normal server code runs on ONE machine. Edge code runs on **many machines distributed around the world**, very close to the user. So an Edge function in Singapore replies fast to a Singapore user.

We mark our card routes as `export const runtime = 'edge'` so they're fast everywhere.

### What is HTTP and why do we use httpx in Python?
HTTP is the language web browsers, servers, and APIs use to talk to each other. It's just text messages: "GET this URL", "Here's the response body".

`httpx` is a Python library that lets your Python code BE a web browser — make HTTP requests, get back responses. We use it when Django needs to fetch the card PNG from Next.js.

### What is "async"?
Normal code runs one line at a time, top to bottom. If line 5 takes 3 seconds (waiting for a network), nothing else happens during those 3 seconds.

`async` code can pause itself while waiting and let OTHER work happen. Then it resumes when the wait is over. Important when you're sending messages to Telegram (which takes time over the network) — you don't want your whole server frozen during the send.

You'll see `async def function_name():` and `await something()` in the bot code. That's all it means: "this function can pause while waiting".

### What is a "signal" in Django?
A way to say: **"when X happens, also run Y"** without coupling X and Y directly.

Example: when a `WaitlistEntry` row is saved in the DB, Django broadcasts a "post_save" signal. Anyone listening can react. Our notification code listens to that signal and queues a card to be sent. The model itself doesn't need to know notifications exist.

Think of it like a doorbell — when the door opens, the bell rings; whoever wants to react to the bell can, but the door doesn't care.

### What is a "task queue" / "worker"?
Some work is slow (sending a Telegram message takes 1-3 seconds). You don't want a user clicking "Submit" to wait that long.

So the API endpoint:
1. Saves the data
2. Drops a "do this thing later" note into a queue
3. Returns immediately to the user (fast!)

Meanwhile a separate process (the **worker**) wakes up, sees the note, and does the slow work in the background.

In Loudrr, the queue is **Redis** (a fast key-value database) and the worker is **django-q2** (a Python library). The qcluster terminal you see when running `dev.ps1` is the worker.

### What is the "transactional outbox" pattern?
A specific way to make sure notifications are NEVER lost AND NEVER sent twice. Here's why it matters:

**Bad approach (don't do this):**
```python
def approve_user(user):
    user.is_approved = True
    user.save()                          # write to DB
    send_telegram_message(user, "...")   # call Telegram API
```

What if `save()` succeeds but Telegram is down? User is approved but never gets the notification. Forever.

**Even worse:** what if `send_telegram_message` succeeds but `save()` then rolls back due to a constraint error? User got the message but isn't actually approved.

**Good approach (transactional outbox):**
```python
def approve_user(user):
    with transaction.atomic():           # everything inside this block is atomic
        user.is_approved = True
        user.save()                      # write to DB
        OutboxEvent.objects.create(...)  # write to DB ("send this later")
    # ↑ Both writes commit together, or both roll back together. Guaranteed.

# Separately, a background worker processes outbox events:
def background_worker():
    for event in OutboxEvent.objects.filter(status='pending'):
        send_telegram_message(...)
        event.status = 'sent'
```

Now: notification can never go out unless the DB change committed. And if Telegram is down, the event stays as PENDING and gets retried later. **Reliable.**

This is the pattern Loudrr uses for every Telegram notification.

---

## Part 4 — Walking through System A (the card image)

**Where it lives:**
```
frontend/app/api/cards/
├── waitlist/route.tsx    ← waitlist confirmation card
└── approval/route.tsx    ← approval card
```

In Next.js, any file named `route.tsx` inside the `app/api/` folder becomes an API endpoint. The folder structure becomes the URL:
- `frontend/app/api/cards/waitlist/route.tsx` → `https://yoursite.com/api/cards/waitlist`
- `frontend/app/api/cards/approval/route.tsx` → `https://yoursite.com/api/cards/approval`

That's a Next.js convention — folder name = URL path.

### Walkthrough of `frontend/app/api/cards/waitlist/route.tsx`

Open the file alongside this doc and follow along.

```tsx
import { ImageResponse } from '@vercel/og'
import { NextRequest } from 'next/server'
```
- `ImageResponse` is the magic class that turns JSX into a PNG.
- `NextRequest` is just the type for the incoming request (gives you query params, headers, etc.).

```tsx
export const runtime = 'edge'
```
- Tells Next.js to run this on Edge servers (fast, distributed).
- Without this, it would run on Node.js (slower cold start).

```tsx
const SPACE_GROTESK_BOLD_URL = 'https://fonts.gstatic.com/s/spacegrotesk/...'
const SYNE_BOLD_URL = 'https://fonts.gstatic.com/s/syne/...'
```
- URLs to font files we want to use in the card.
- We can't use CSS `@font-face` here — Satori needs the actual font bytes. So we'll fetch them at request time.

```tsx
export async function GET(request: NextRequest) {
```
- Handles GET requests to this URL.
- The `async` means this function can do slow things (like fetch fonts) without blocking.

```tsx
  const [syneFontData, spaceGroteskFontData] = await Promise.all([
    fetch(SYNE_BOLD_URL).then(res => res.arrayBuffer()),
    fetch(SPACE_GROTESK_BOLD_URL).then(res => res.arrayBuffer()),
  ])
```
- Downloads both fonts in parallel (saves time vs sequential).
- `arrayBuffer()` converts the response to raw bytes — what Satori needs.
- `await Promise.all([...])` means: do both, wait until both are done.

```tsx
  const url = new URL(request.url)
  const LOGO_URL = `${url.origin}/loudrr-icon-small.png`

  const { searchParams } = url
  const xUsername = searchParams.get('username') || 'user'
```
- Parses the request URL.
- `url.origin` is "https://yoursite.com" — we use it to build a logo URL on the same domain.
- `searchParams.get('username')` reads the `?username=...` query param. If missing, defaults to `'user'`.

```tsx
  return new ImageResponse(
    ( <div style={{...}}> ...JSX... </div> ),
    { width: 1012, height: 638, fonts: [...] }
  )
```
- Returns the image. The first argument is the JSX. The second is config (size + fonts).
- Satori walks the JSX, applies the styles, lays it out, rasterizes to PNG, and returns the bytes.

### Why some CSS rules are weird (Satori limitations)

You'll notice every container has `display: 'flex'` even when it doesn't need flex layout. That's because **Satori requires `display: flex` on every parent of multiple children**. It doesn't support `display: block` (the normal CSS default).

Other common gotchas:
- `position: 'absolute'` children need explicit `width` and `height` (no auto-sizing)
- No `media queries`, no `:hover`, no animations
- `boxShadow` works but limited
- `backgroundImage` with `url(data:image/svg+xml,...)` works for patterns
- Flex `gap` works (huge relief when laying out)

If you wanted to test this yourself: change a value in the JSX, save the file, refresh the browser URL. Instant feedback.

---

## Part 5 — Walking through System B (Django delivery)

This is more involved. We'll trace what happens when a user submits the waitlist form.

### Step-by-step

#### 1. User submits the form (frontend)

The mini-app in `frontend/app/app/page.tsx` calls `api.registerWaitlist(...)` which makes a POST request to `/api/miniapp/waitlist/register/`.

#### 2. Django view receives it

**File:** `backend/miniapp/views.py` — class `WaitlistRegisterView`

The view validates the data, then:

```python
with transaction.atomic():
    entry = WaitlistEntry.objects.create(
        email=email,
        telegram_id=telegram_id,
        x_username=x_username,
        status=WaitlistEntry.Status.SUBMITTED,
        # ... other fields
    )
```

`transaction.atomic()` is a Django thing: everything inside this block either ALL commits or ALL rolls back. If anything below `entry.create()` fails, the entry creation also gets undone. This is what makes the transactional outbox work.

The line `WaitlistEntry.objects.create(...)` is Django ORM (Object-Relational Mapping). It generates a SQL `INSERT` statement and runs it on the database. You don't write SQL directly — the ORM writes it for you.

#### 3. Django fires a signal

When `WaitlistEntry.objects.create()` finishes, Django automatically broadcasts a signal called `post_save`. Any function that's "subscribed" to this signal runs.

**File:** `backend/core/signals.py:127` — `send_submission_confirmation_on_submit`

```python
@receiver(post_save, sender=WaitlistEntry)
def send_submission_confirmation_on_submit(sender, instance, created, **kwargs):
    if instance.status != WaitlistEntry.Status.SUBMITTED:
        return  # not what we care about, exit
    if previous_status == WaitlistEntry.Status.SUBMITTED:
        return  # was already submitted, no need to re-notify

    OutboxService.queue_waitlist_submitted(...)
```

The decorator `@receiver(post_save, sender=WaitlistEntry)` means "run this function when any WaitlistEntry is saved". Standard Django pattern.

We don't send the Telegram message HERE. We just write a row to the `outbox_events` table that says "Hey worker, please send a submission card to this user".

Why not send directly? Because:
- The user is waiting for the API response. Sending Telegram takes 1-3 seconds.
- If Telegram is down, the user's submission would fail too.
- This way: instant API response, notification gets retried automatically.

#### 4. After the DB transaction commits, kick the worker

```python
def trigger_processing():
    async_task("core.tasks.process_pending_outbox_events", batch_size=10)

transaction.on_commit(trigger_processing)
```

`transaction.on_commit(...)` says: "after the database transaction successfully commits, then run this callback". If the transaction rolls back, the callback never runs. This prevents a race where the worker tries to read a row that doesn't exist yet.

`async_task("core.tasks.process_pending_outbox_events", batch_size=10)` is django-q2's way of saying "queue this function to run in the background worker". It writes a small message to Redis, and the qcluster worker (in another terminal/process) picks it up.

#### 5. Worker picks up the task

In your `dev.ps1` you have a `django-q2 cluster` tab running. That's the worker. It connects to Redis and waits for tasks.

When it sees the new task, it calls `process_pending_outbox_events(batch_size=10)`.

**File:** `backend/core/tasks.py:120`

```python
def process_pending_outbox_events(batch_size: int = 50):
    pending_events = OutboxEvent.objects.filter(status='pending')[:batch_size]
    for event in pending_events:
        OutboxService.process_event(event)
```

It reads the pending events from the DB, processes each one.

#### 6. Process_event routes to the right handler

**File:** `backend/core/services/outbox.py:326`

```python
def process_event(event: OutboxEvent) -> bool:
    event.mark_processing()  # set status to PROCESSING

    try:
        if event.event_type == OutboxEvent.EventType.WAITLIST_SUBMITTED:
            success = OutboxService._process_waitlist_submitted(event)
        elif event.event_type == OutboxEvent.EventType.WAITLIST_APPROVED:
            success = OutboxService._process_waitlist_approved(event)
        # ... other types

        if success:
            event.mark_sent()
            return True
        else:
            event.mark_failed("Processing returned False")
            return False
    except Exception as e:
        event.mark_failed(str(e))
        return False
```

This is a router. Based on the event type, it calls the right handler. If anything fails, it marks the event as FAILED so we can retry later.

#### 7. The waitlist-specific handler

**File:** `backend/core/services/outbox.py:411`

```python
def _process_waitlist_submitted(event: OutboxEvent) -> bool:
    entry = WaitlistEntry.objects.get(id=event.payload["entry_id"])

    # send_waitlist_confirmation is async, but our worker is sync.
    # So we create a fresh asyncio event loop to run it.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(send_waitlist_confirmation(entry))
        return result
    finally:
        loop.close()
```

This is just plumbing to bridge sync code (the worker) and async code (the Telegram library). The actual work happens in `send_waitlist_confirmation()`.

#### 8. Build the Telegram message

**File:** `backend/bots/telegram/notifications.py:68`

```python
async def send_waitlist_confirmation(entry: WaitlistEntry) -> bool:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    # Step 8a: Get the card PNG (via System A)
    card_image = create_waitlist_card(x_username=entry.x_username)

    # Step 8b: Send to Telegram
    await bot.send_photo(
        chat_id=entry.telegram_id,
        photo=card_image,
        caption="*You're on the Loudrr waitlist!*\n\nX: @{x_username}\n\n_We'll notify..._",
        parse_mode="Markdown"
    )
```

`Bot(token=...)` creates a Telegram bot client. `bot.send_photo(...)` makes an HTTPS POST to `api.telegram.org` with our bot token and the photo. Telegram delivers it to the user.

`parse_mode="Markdown"` means asterisks become **bold** and underscores become _italic_ in the caption.

#### 9. The bridge — fetching the card PNG

**File:** `backend/bots/telegram/image_utils.py:15`

```python
def create_waitlist_card(x_username: str, ...) -> io.BytesIO:
    # Build the URL — same one you'd hit in browser
    params = {"username": x_username, ...}
    url = f"{LANDING_URL}/api/cards/waitlist?{urlencode(params)}"

    # HTTP GET to Next.js (System A)
    with httpx.Client(timeout=30) as client:
        response = client.get(url)

    # Wrap bytes as a file-like object so python-telegram-bot can upload it
    output = io.BytesIO(response.content)
    output.seek(0)
    return output
```

This is the bridge between System B (Django) and System A (Next.js). Django literally does an HTTP GET to its own Next.js card endpoint, just like your browser would.

`io.BytesIO(...)` wraps raw bytes as a file-like object. That's what `bot.send_photo()` expects — something that behaves like a file you can read from.

`output.seek(0)` resets the read position to the start. After writing to a BytesIO, the cursor is at the end; if you don't seek to 0, reading gives you nothing.

---

## Part 6 — The full picture (sequence diagram)

```
User submits waitlist form
        │
        ▼
Django view: WaitlistRegisterView.post()
        │
        │ INSERT WaitlistEntry  (atomic transaction)
        ▼
Postgres DB
        │
        │ post_save signal fires
        ▼
signals.py: send_submission_confirmation_on_submit
        │
        │ INSERT OutboxEvent  (same atomic transaction)
        ▼
outbox_events table  (status=PENDING)
        │
        │ on transaction commit → enqueue task in Redis
        ▼
qcluster worker picks up task
        │
        │ process_pending_outbox_events()
        │   → process_event(event)
        │     → _process_waitlist_submitted(event)
        │       → send_waitlist_confirmation(entry)
        │         → create_waitlist_card(x_username)
        ▼
HTTP GET to Next.js: /api/cards/waitlist?username=...
        │
        │ JSX renders to PNG
        ▼
PNG bytes returned
        │
        ▼
bot.send_photo(chat_id, photo=PNG, caption="...")
        │
        │ HTTPS POST to api.telegram.org
        ▼
Telegram delivers card to user's chat ✓
```

---

## Part 7 — How to debug each layer (practical)

When something breaks, you need to know WHERE in this chain it broke. Here's how to inspect each layer:

| Layer | How to check |
|-------|--------------|
| Card design itself | Open URL in browser: `http://localhost:3000/api/cards/waitlist?username=test`. If broken, the card route is broken — fix the JSX. |
| API endpoint receiving form | Browser DevTools → Network tab. Submit form. Find the `/waitlist/register/` request. Check status code (should be 200). |
| WaitlistEntry created in DB | Open `/admin/core/waitlistentry/`. Refresh after submitting. New row should appear. |
| Signal fired | Add `logger.info("signal fired!")` at top of signal handler. Submit form. Check Django runserver tab for the log line. |
| OutboxEvent queued | Open `/admin/core/outboxevent/`. New row should appear with status=PENDING immediately after submission. |
| Worker picked up task | Watch the qcluster terminal tab. You'll see `Processing 'core.tasks.process_pending_outbox_events' ...`. |
| Telegram delivery | If everything above worked, the card lands in the user's Telegram chat. If not, the qcluster terminal will show the exception. |

---

## Part 8 — Why this design over alternatives

You might wonder why we don't just:

**Q: Why not have Django generate the card image too?**
A: Django would need to use a library like Pillow (Python imaging) and manually draw the layout. Tedious, slow, and changes require Python code. With our setup, designers/devs edit JSX (familiar React-like syntax) and refresh the browser — instant preview.

**Q: Why not just put the card image in the Telegram message URL?**
A: Telegram doesn't take URLs for photos — it uploads the bytes itself. So we have to fetch the bytes server-side and forward them.

**Q: Why use a queue (django-q2)? Why not just send synchronously?**
A: Two reasons. First, Telegram API takes 1-3 seconds — bad UX to make the user wait. Second, retries: if Telegram is briefly down, the queue auto-retries; synchronous code would just fail.

**Q: Why an OutboxEvent and not just async_task() directly?**
A: `async_task()` writes to Redis. If your DB transaction rolls back AFTER the Redis write, you'd send a notification for an event that never actually happened. The outbox pattern guarantees the notification only goes out if the DB change actually committed (because both writes are in the same transaction).

---

## Part 9 — Glossary (look up terms here)

| Term | Plain English |
|------|----------------|
| API endpoint | A URL that runs code when visited |
| HTTP / HTTPS | The protocol web browsers and servers use to talk |
| GET / POST | Two types of HTTP requests (read / write) |
| JSX | HTML written inside JavaScript |
| Edge function | Code that runs on many servers worldwide for low latency |
| Async / await | Code that can pause while waiting for slow things |
| Django ORM | Python objects that auto-generate SQL queries |
| Migration | A script that changes the DB schema (add column, etc.) |
| Signal | "When X happens, also do Y" pattern |
| Queue | A list of "things to do later" |
| Worker | A background process that takes things off a queue and does them |
| Transaction | A group of DB operations that all succeed together or all fail together |
| Outbox pattern | Storing notifications in the DB first, then sending them later, to guarantee reliability |
| Redis | A super-fast in-memory database often used as a queue |
| Telegram Bot API | HTTP API that lets your code send messages as a bot |
| Webhook | When an external service POSTs to YOUR server (vs you polling them) |

---

## Part 10 — Suggested next steps for learning

1. **Open the URLs in your browser** and look at the cards
   - http://localhost:3000/api/cards/waitlist?username=0xBlest_
   - http://localhost:3000/api/cards/approval?username=0xBlest_

2. **Edit the JSX** (e.g., change the title text in `frontend/app/api/cards/waitlist/route.tsx`). Save. Refresh the browser. See the change instantly.

3. **Submit a waitlist entry** via the mini-app at `localhost:3000/app`. Watch:
   - The Django runserver tab — see the request log
   - The qcluster tab — see the worker process the event
   - The admin `/admin/core/outboxevent/` — see the event change from PENDING → SENT

4. **Read these files** in order (they get progressively deeper):
   - `frontend/app/api/cards/waitlist/route.tsx` — start with what you can see
   - `backend/bots/telegram/notifications.py` — short, just builds a Telegram message
   - `backend/bots/telegram/image_utils.py` — even shorter, the bridge
   - `backend/core/signals.py` — the trigger
   - `backend/core/services/outbox.py` — the queue logic
   - `backend/core/tasks.py` — the worker functions

5. **Run a card change end-to-end**:
   - Change the waitlist card title from "You're on the Waitlist!" to something else
   - Save the file
   - Trigger a new waitlist submission
   - Watch the new card arrive in your Telegram

That's the loop. Once you're comfortable with this loop, every other feature in Loudrr follows the same pattern: API endpoint → DB save → signal → outbox event → worker → external action.
</content>
</invoke>