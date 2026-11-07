FROM python:3.11-slim

# Cài đặt FFmpeg và Node.js (dành cho YouTube signature extraction của yt-dlp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn
COPY . .

# Tạo thư mục tạm và thư mục data
RUN mkdir -p /app/temp /app/data

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATABASE_PATH=/app/data/music.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

