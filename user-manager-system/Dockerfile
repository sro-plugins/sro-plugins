FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements if we had a requirements.txt, 
# but since it's a small app we'll install directly to keep it simple or create one
RUN pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-multipart python-dotenv

# Copy application code
COPY . .

# Create directory for files if they don't exist
RUN mkdir -p files/sc files/caravan

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
