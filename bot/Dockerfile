FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY run.py .
COPY .env.example .env

# Create volume mount points
VOLUME ["/app/data"]

# Run the bot
CMD ["python", "run.py"]

