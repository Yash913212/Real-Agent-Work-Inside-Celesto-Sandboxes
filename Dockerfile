FROM python:3.11-slim

# Install system dependencies including curl for healthcheck and postgres client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files, seeds, reports, and logs
COPY src/ ./src/
COPY seeds/ ./seeds/
COPY reports/ ./reports/
COPY logs/ ./logs/

EXPOSE 8080

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080"]
