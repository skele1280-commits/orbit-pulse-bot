FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg for yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot and cookies
COPY main.py .
COPY cookies_filtered.txt .

# Run
CMD ["python", "main.py"]
