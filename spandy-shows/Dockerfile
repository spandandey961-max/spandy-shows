FROM node:24-bookworm-slim AS frontend
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public
RUN pnpm run build

FROM docker:28-cli AS docker-cli
FROM python:3.12-slim-bookworm
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend ./backend
COPY migrations ./migrations
COPY --from=frontend /app/dist ./dist
RUN mkdir /jobs
ENV SPANDY_EXECUTION_MODE=docker SPANDY_JOB_ROOT=/jobs PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
