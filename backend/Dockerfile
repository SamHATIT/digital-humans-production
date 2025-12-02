FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js for SF CLI
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Salesforce CLI
RUN npm install -g @salesforce/cli

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-docx openai==1.3.7

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
