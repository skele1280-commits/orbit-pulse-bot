# ⚡ Super Simple YouTube Setup (5 minutes)

You're tired! This is the EASIEST way:

## Step 1: Open cookies.txt

Open the `cookies.txt` file you downloaded (the one from the browser extension).

## Step 2: Copy Everything

Select ALL text in the file (Ctrl+A or Cmd+A), then copy (Ctrl+C or Cmd+C).

## Step 3: Railway Dashboard

1. Go to: https://railway.com/project/f58910dd-c6c4-45cf-b735-bd2c3f32d038
2. Click your service
3. Click **Variables** tab
4. Click **+ New Variable**
5. Name: `YOUTUBE_COOKIES`
6. Value: **Paste** the entire cookies.txt content
7. Click **Add**
8. Railway auto-deploys (wait 2 minutes)

## Step 4: Test

Send that YouTube link again → `/grab`

Should work now! 🎉

---

**That's it!** Just one copy-paste. No file uploads needed.

The bot reads cookies from the environment variable and creates a temp file automatically.
