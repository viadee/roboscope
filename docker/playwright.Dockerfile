FROM mcr.microsoft.com/playwright:v1.50.0-noble

WORKDIR /app
COPY e2e/package*.json ./
RUN npm ci

COPY e2e/ .
ENV CI=1
CMD ["npx", "playwright", "test"]
