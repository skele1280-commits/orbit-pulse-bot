FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg for yt-dlp)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY main.py simple_downloader.py ./

# Run bot
CMD ["python", "main.py"]
