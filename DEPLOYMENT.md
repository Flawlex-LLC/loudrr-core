# ECHO Bot - Deployment Guide

## Deploying Telegram Bot to Hetzner with Coolify

Since Telegram API is blocked locally, we'll deploy just the bot to your Hetzner server while keeping development local.

### Prerequisites

1. Hetzner server with Coolify installed
2. Git repository (GitHub/GitLab) to push your code
3. Supabase database URL (already configured)
4. Telegram bot token (already configured)

### Step 1: Push Code to Git Repository

```bash
cd c:\Users\mamoo\projects\reply-community-bot
git init
git add .
git commit -m "Initial ECHO bot setup"
git remote add origin <your-git-repo-url>
git push -u origin main
```

### Step 2: Configure Coolify

1. Log into your Coolify dashboard
2. Create a new application
3. Select "Git Repository" as source
4. Connect your repository
5. Set build pack to "Dockerfile"
6. Point to root directory (Dockerfile is in root)

### Step 3: Set Environment Variables in Coolify

Add these environment variables in Coolify:

```env
# Django
SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,your-server-ip
DJANGO_SETTINGS_MODULE=echo.settings

# Database (Supabase)
DATABASE_URL=postgresql://postgres:qShQXGbylufkFpFY@db.ydptmgxwprydnwdjawqo.supabase.co:5432/postgres

# Telegram Bot
TELEGRAM_BOT_TOKEN=8502177179:AAH6Ec1naUJXg0zDXufiB3w3XsUDUu1rHJU

# Encryption (generate a new 32-byte key for production)
ENCRYPTION_KEY=your-32-byte-encryption-key-here

# Redis (optional for now)
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

**Important:** Generate a new SECRET_KEY and ENCRYPTION_KEY for production:
```python
# SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# ENCRYPTION_KEY (32 bytes)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 4: Deploy

1. Click "Deploy" in Coolify
2. Coolify will:
   - Clone your repository
   - Build the Docker image
   - Run migrations automatically
   - Start the Telegram bot

### Step 5: Verify Deployment

Check Coolify logs to ensure:
- Migrations ran successfully
- Bot connected to Telegram API
- No errors in startup

Test the bot:
1. Open Telegram
2. Search for your bot
3. Send `/start`
4. You should get the welcome message

### Step 6: Monitor

- Check logs in Coolify dashboard
- Monitor database in Supabase dashboard
- Test all bot commands:
  - `/start` - Onboarding
  - `/balance` - Check credits
  - `/feed` - Get posts to engage
  - `/post` - Submit a post
  - `/leaderboard` - Top engagers
  - `/stats` - Your statistics

## Local Development

While the bot runs on Hetzner, continue development locally:

1. Make changes to code locally
2. Test with Django development server: `python manage.py runserver`
3. Test database operations
4. When ready, push to git: `git push origin main`
5. Coolify will auto-deploy (if auto-deploy enabled) or manually trigger deploy

## Troubleshooting

### Bot not connecting to Telegram
- Verify TELEGRAM_BOT_TOKEN in Coolify environment variables
- Check Coolify logs for connection errors
- Ensure Hetzner server has outbound internet access

### Database connection issues
- Verify DATABASE_URL is correct in Coolify
- Check Supabase connection limits
- Ensure Supabase allows connections from Hetzner IP

### Migrations not running
- Check Coolify build logs
- Manually run: `docker exec <container-name> python manage.py migrate`

## Next Steps

1. **Test bot thoroughly** - All commands, error cases
2. **Add Discord bot** - Phase 4
3. **Monitor usage** - Supabase dashboard for data
4. **Scale if needed** - Upgrade Hetzner resources

## Rollback

If deployment fails:
1. Check previous deployment in Coolify
2. Click "Rollback" to previous version
3. Or fix locally and push again
