FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install typical desktop fonts to pass fingerprinting
RUN apt-get update && apt-get install -y fonts-liberation fonts-noto-color-emoji && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080
CMD ["python", "app.py"]
