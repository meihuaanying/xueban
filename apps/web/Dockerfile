# 官网/家长端/后台（Next.js standalone）
# 构建上下文为仓库根目录：docker compose -f infra/docker/docker-compose.prod.yml build web
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

WORKDIR /app

# 先装依赖（利用层缓存）
COPY .npmrc pnpm-workspace.yaml package.json pnpm-lock.yaml turbo.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/core/package.json packages/core/package.json
COPY packages/ui/package.json packages/ui/package.json
COPY packages/config/package.json packages/config/package.json

RUN pnpm install --frozen-lockfile --filter @xueban/web...

# 再拷源码构建
COPY packages ./packages
COPY apps/web ./apps/web

# 构建期公开变量（同源网关：NEXT_PUBLIC_API_BASE_URL 应与站点同源）
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_RELEASE_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL} \
    NEXT_PUBLIC_RELEASE_BASE_URL=${NEXT_PUBLIC_RELEASE_BASE_URL}
RUN pnpm --filter @xueban/web build

FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]

CMD ["node", "apps/web/server.js"]
