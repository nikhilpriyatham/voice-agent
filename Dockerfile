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

# Set environment variables - UVICORN_HOST forces uvicorn to bind to 0.0.0.0
ENV HOST=0.0.0.0
ENV PORT=7860
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=7860

EXPOSE 7860

# Run pipecat runner - UVICORN_HOST env var should force 0.0.0.0 binding
CMD ["python", "-m", "pipecat.runner.run", "bot:bot"]
