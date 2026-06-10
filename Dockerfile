FROM python:3.11-slim

WORKDIR /app

# Node.js required for MongoDB MCP server (spawned as subprocess by ADK)
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pre-install MongoDB MCP server so npx never downloads at runtime
RUN npm install -g mongodb-mcp-server

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# ADK's built-in server — serves your app/agent.py root_agent
# AND mounts any FastAPI app you add on top
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port $PORT"]