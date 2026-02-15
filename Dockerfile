FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-multipart python-dotenv

# Copy application code (now in root)
COPY . .

# Create directory for files if they don't exist
RUN mkdir -p files/sc files/caravan files/feature

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
