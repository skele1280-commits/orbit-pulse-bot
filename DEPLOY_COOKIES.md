# 🍪 Deploy YouTube Cookies to Railway

## Step 1: Upload cookies_filtered.txt

The filtered cookies file is ready at: `cookies_filtered.txt` (42 lines, ~5KB)

### Option A: Railway Volumes (Recommended)

1. Go to Railway Dashboard: https://railway.com/project/f58910dd-c6c4-45cf-b735-bd2c3f32d038
2. Click your **orbit-pulse-bot** service
3. Go to **Settings** tab
4. Scroll to **Volumes** section
5. Click **+ New Volume**
6. **Mount Path:** `/app/cookies_filtered.txt`
7. Upload file: `cookies_filtered.txt` from your repo
8. Click **Deploy**

### Option B: Include in Dockerfile (Alternative)

If Volumes doesn't work:

1. Git commit and push `cookies_filtered.txt`
2. Update Dockerfile to copy it:
   ```dockerfile
   COPY cookies_filtered.txt .
   ```
3. Railway auto-deploys

## Step 2: Test

Once deployed:
1. Send an age-restricted YouTube link to bot
2. Use `/grab`
3. Should download successfully! ✅

## How It Works

The bot checks for cookies in this order:
1. `/app/cookies_filtered.txt` (Railway volume)
2. `./cookies_filtered.txt` (local file)
3. `YOUTUBE_COOKIES` env var (fallback)

## Security Note

⚠️ `cookies_filtered.txt` contains ONLY essential YouTube auth cookies (39 lines filtered from 2713).
Includes: CONSENT, VISITOR_INFO, LOGIN_INFO, session tokens.
Does NOT include: tracking cookies, ads cookies, unnecessary data.

Still treat as sensitive - never commit to public repos!
