# Medical AI Gateway — frontend image. Multi-stage: build deps → standalone runtime.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
# No lockfile committed at scaffold stage; `npm install` generates it. In a real
# repo you'd commit package-lock.json and use `npm ci` for reproducible builds.
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# `output: 'standalone'` emits a minimal server in .next/standalone.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
