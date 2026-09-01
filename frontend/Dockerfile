# Kairos frontend: Next.js standalone output, non-root, minimal runtime.
# Build context: repository root (the legal sync script reads the root
# PRIVACY.md / TERMS.md during build):
#   docker build -f frontend/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/scripts ./scripts
COPY PRIVACY.md TERMS.md ./
COPY frontend/ .
RUN node scripts/sync-legal.mjs
# NEXT_PUBLIC vars must exist at build time to be inlined in the bundle.
ARG NEXT_PUBLIC_API_DOCS_URL=""
ARG NEXT_PUBLIC_TEMPORAL_UI_URL=""
ENV NEXT_PUBLIC_API_DOCS_URL=$NEXT_PUBLIC_API_DOCS_URL
ENV NEXT_PUBLIC_TEMPORAL_UI_URL=$NEXT_PUBLIC_TEMPORAL_UI_URL
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -g 10001 -S kairos && adduser -u 10001 -S kairos -G kairos

COPY --from=builder --chown=kairos:kairos /app/.next/standalone ./
COPY --from=builder --chown=kairos:kairos /app/.next/static ./.next/static

USER kairos
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1

CMD ["node", "server.js"]
