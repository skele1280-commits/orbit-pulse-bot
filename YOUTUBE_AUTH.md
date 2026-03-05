# YouTube Authentication Setup

To download age-restricted videos, the bot needs YouTube cookies.

## Quick Setup (Browser Extension)

### Option 1: Get cookies.txt LOCALLY Extension (Chrome/Firefox)

1. **Install Extension:**
   - Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   - Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/

2. **Export Cookies:**
   - Go to https://youtube.com and **log in**
   - Click the extension icon
   - Click "Export" → Save as `cookies.txt`

3. **Upload to Railway:**
   - Railway Dashboard → Your Service → Variables
   - Add file: `cookies.txt` → Upload your cookies file
   - Or use Railway CLI: `railway run --volume cookies.txt:/app/cookies.txt`

## Alternative: Manual Cookie Export

If you can't use extensions, export manually:

1. Open YouTube in your browser (logged in)
2. Press F12 (Developer Tools)
3. Go to Application → Cookies → https://youtube.com
4. Copy all cookies and format as Netscape format

## Netscape Cookie Format

```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	0	CONSENT	YES+1
.youtube.com	TRUE	/	FALSE	1234567890	VISITOR_INFO1_LIVE	xxxxx
```

## Security Note

⚠️ **Keep your cookies.txt private!** Never commit it to GitHub.
Cookies contain your YouTube session - treat them like passwords.

The bot only uses cookies for yt-dlp downloads, nothing else.

## Test

Once cookies are uploaded:
1. Restart the bot
2. Try downloading an age-restricted video
3. Should work now!

## Troubleshooting

**"Still can't download":**
- Cookies might be expired (re-export fresh ones)
- Make sure cookies.txt is in `/app/` directory on Railway
- Check Railway logs for "Using cookies from..."

**"Cookies not found":**
- File must be named exactly `cookies.txt`
- Must be in the same directory as `main.py`
- Check file size: should be >200 bytes

---

If you see `[DOWNLOAD] Using cookies from cookies.txt` in logs → it's working!
