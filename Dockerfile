FROM dailyco/pipecat-base:latest

WORKDIR /app

# Copy requirements and install
COPY server/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy server files
COPY server/ .

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=7860

EXPOSE 7860

# Run with explicit host binding
CMD ["python", "-m", "pipecat.runner.run", "--host", "0.0.0.0", "--port", "7860", "bot:bot"]
