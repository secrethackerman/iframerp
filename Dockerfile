FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install Xvfb for headful mode in Docker, plus fonts for fingerprinting
RUN apt-get update && apt-get install -y xvfb fonts-liberation fonts-noto-color-emoji && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Patchright's patched Chromium binary
RUN patchright install chromium

COPY app.py .

# Set display for Xvfb
ENV DISPLAY=:99

# Start Xvfb in the background, then start the app
CMD Xvfb :99 -screen 0 1920x1080x24 & python app.py
