FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
COPY server/requirements.txt server/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set working directory to server
WORKDIR /app/server

# Run the bot
CMD ["python", "bot.py"]
