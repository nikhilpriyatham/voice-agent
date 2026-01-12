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

# Copy requirements first for caching
COPY requirements.txt .
COPY server/requirements.txt server/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set working directory to server
WORKDIR /app/server

# Set environment for Railway - bind to all interfaces
ENV HOST=0.0.0.0
ENV PORT=7860

# Expose port for WebRTC
EXPOSE 7860

# Run the bot with host binding
CMD ["python", "bot.py"]
