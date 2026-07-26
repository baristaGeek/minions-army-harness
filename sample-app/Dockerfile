# syntax=docker/dockerfile:1

# ---- Base ----
FROM node:22-slim AS base
# Prisma needs openssl at build and runtime.
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# ---- Dependencies ----
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

# ---- Build ----
FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `npm run build` runs `prisma generate && next build`.
RUN npm run build

# ---- Runner ----
FROM base AS runner
ENV NODE_ENV=production
ENV PORT=3000
# Copy the fully built app (including node_modules with the generated Prisma
# client and CLI) so `next start`, `prisma migrate deploy`, and `prisma db seed`
# all work from the same image.
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "run", "start"]
