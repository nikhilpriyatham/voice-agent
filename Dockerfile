FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy everything first
COPY . .

# Install dependencies from root requirements.txt (which references server/requirements.txt)
RUN pip install -r requirements.txt

# Set working directory to server
WORKDIR /app/server

# Set environment variables - let Railway set PORT dynamically
ENV HOST=0.0.0.0

# Run bot_runner which manages Daily rooms and spawns bots
CMD ["python", "bot_runner.py"]
