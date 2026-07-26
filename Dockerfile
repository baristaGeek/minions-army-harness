FROM python:3.13-slim

WORKDIR /app

# Install system dependencies. curl + flyctl are needed so the API can launch
# ephemeral minion machines via `flyctl machine run` (MINION_EXECUTION_BACKEND=fly_machines).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://fly.io/install.sh | sh
ENV PATH="/root/.fly/bin:${PATH}"

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and migrations
COPY minions_army/ ./minions_army/
COPY user_data/ ./user_data/
COPY alembic.ini .
COPY alembic/ ./alembic/

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "minions_army.infrastructure.api.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
