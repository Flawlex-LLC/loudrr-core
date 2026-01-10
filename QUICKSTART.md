# ECHO - Quick Setup Guide for Cloud Development

## Step 1: Create GitHub Repository (2 min)

1. Go to https://github.com/new
2. Repository name: `echo-bot` (or any name you prefer)
3. **Keep it Private** (contains sensitive data)
4. **DO NOT** initialize with README (we have code already)
5. Click "Create repository"
6. Copy the repository URL (e.g., `https://github.com/yourusername/echo-bot.git`)

## Step 2: Initialize Git & Push Code (2 min)

Open terminal in project directory and run:

```bash
cd c:\Users\mamoo\projects\reply-community-bot

# Initialize git
git init

# Add all files
git add .

# Create first commit
git commit -m "Initial ECHO bot setup"

# Add your GitHub repo (replace with your URL)
git remote add origin https://github.com/YOUR-USERNAME/echo-bot.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Note:** GitHub will ask for authentication. Use a Personal Access Token (PAT) if needed.

## Step 3: Set Up Coolify (5 min)

### 3.1 Create New Application

1. Log into your Coolify dashboard
2. Click "New Resource" → "Application"
3. Select "Public Repository" or "Private Repository" (if private, connect GitHub)

### 3.2 Configure Build

- **Build Pack:** Dockerfile
- **Dockerfile Location:** `./Dockerfile`
- **Base Directory:** `/` (root)
- **Branch:** `main`

### 3.3 Add Environment Variables

Click "Environment Variables" and add these:

```env
SECRET_KEY=dar5*a6pu71y0mqg(0y-jnma8)%^uop8@c)75b6@*dm$gfwgh-
DEBUG=False
ALLOWED_HOSTS=*
DJANGO_SETTINGS_MODULE=echo.settings

DATABASE_URL=postgresql://postgres:qShQXGbylufkFpFY@db.ydptmgxwprydnwdjawqo.supabase.co:5432/postgres

TELEGRAM_BOT_TOKEN=8502177179:AAH6Ec1naUJXg0zDXufiB3w3XsUDUu1rHJU

ENCRYPTION_KEY=ec4w_v8WRRC4afR7IL9fWRQhQ693gPqKK1gGByhXicI=

REDIS_URL=redis://localhost:6379/0

CORS_ALLOWED_ORIGINS=http://localhost:3000
```

### 3.4 Enable Auto Deploy

- Toggle "Auto Deploy" to ON
- This will rebuild and restart bot on every git push

### 3.5 Deploy

- Click "Deploy"
- Wait 2-3 minutes for build
- Check logs for "Bot is running"

## Step 4: Test the Bot (1 min)

1. Open Telegram
2. Search for your bot
3. Send `/start`
4. You should get a welcome message!

## Step 5: Development Workflow

Now you can develop quickly:

```bash
# 1. Make changes locally (edit files in VSCode)

# 2. Commit and push
git add .
git commit -m "Added new feature"
git push

# 3. Wait 30-60 seconds for Coolify to auto-deploy

# 4. Test in Telegram immediately

# 5. Check logs in Coolify dashboard if needed
```

## Monitoring & Debugging

**View Logs:**
- Coolify Dashboard → Your App → Logs tab
- See real-time bot output

**Common Issues:**

1. **Bot not responding**
   - Check Coolify logs for errors
   - Verify TELEGRAM_BOT_TOKEN is correct
   - Ensure bot is running (not crashed)

2. **Database errors**
   - Verify DATABASE_URL is correct
   - Check Supabase connection limits
   - Run migrations: `python manage.py migrate` (in Coolify terminal)

3. **Build fails**
   - Check Dockerfile syntax
   - Verify requirements.txt has all dependencies
   - Check Coolify build logs

## Quick Commands

**Manually restart bot in Coolify:**
```bash
# In Coolify terminal/SSH
docker restart <container-name>
```

**Run migrations manually:**
```bash
# In Coolify terminal
docker exec <container-name> python manage.py migrate
```

**Check Django admin:**
```bash
# Create superuser
docker exec -it <container-name> python manage.py createsuperuser
```

## Next Steps

Once bot is running:
1. Test all commands: `/start`, `/feed`, `/post`, `/balance`, `/stats`, `/leaderboard`
2. Check database in Supabase to see data being created
3. Invite test users to try it out
4. Iterate on features (edit locally → push → test in Telegram)

---

**Need help?** Check logs in Coolify or ask for assistance.
