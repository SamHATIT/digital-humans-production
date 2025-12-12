FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js for SF CLI + Chrome dependencies for Mermaid
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    gnupg \
    build-essential \
    # Chrome/Puppeteer dependencies for Mermaid diagram generation
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libpango-1.0-0 \
    libcairo2 \
    libnss3 \
    libnspr4 \
    libx11-xcb1 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Salesforce CLI
RUN npm install -g @salesforce/cli

# Install Mermaid CLI for diagram generation
RUN npm install -g @mermaid-js/mermaid-cli

# Create puppeteer config for running as root (--no-sandbox)
RUN mkdir -p /root && echo '{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}' > /tmp/puppeteer-config.json

# === OPTIMIZATION: Install PyTorch CPU-only FIRST ===
# This prevents sentence-transformers from pulling the GPU version (6GB -> 200MB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Python dependencies (includes chromadb, anthropic, openai, sentence-transformers, etc.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
