FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for yt-dlp and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY main.py technical_analysis.py simple_downloader.py ./

# Run bot
CMD ["python", "main.py"]
