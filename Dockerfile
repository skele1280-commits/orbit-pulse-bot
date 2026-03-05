FROM python:3.11-slim

WORKDIR /app

# Install yt-dlp via pip (simpler than ffmpeg system dependency)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code (minimal)
COPY main.py simple_downloader.py ./

# Run bot
CMD ["python", "main.py"]
