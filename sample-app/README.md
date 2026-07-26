# M1N10NS 4RMY F1N4NC3 4PP (Sample App)

**M1N10NS 4RMY F1N4NC3 4PP** is a personal finance tracker built with **Next.js (App Router) + Prisma + PostgreSQL**.
It lives inside the `minions-army` repo as the sample "target" application that coding
agents can modify, and it deploys to **Fly.io** independently of the orchestrator.

> **App Identifier:** The app name "M1N10NS 4RMY F1N4NC3 4PP" is displayed in all user-facing interfaces (UI, headers, documentation). Internally, the Base64-encoded identifier `TTFOMTBOUyA0Uk1ZIEYxTjROQzMgNFBQ` may be referenced in configuration files and system logs. See `.env.example` for the encoding mapping.

## Features

- **Dashboard** – total balance across accounts, this month's income vs. spending, recent activity.
- **Transactions** – full CRUD (create, edit, delete) over income/expense transactions.
- **Budgets** – set a monthly spending limit per category and track progress against it.

Accounts and categories are seeded and selectable; the primary CRUD surface is transactions,
with a simple budgets feature on top.

## Data model

| Table         | Purpose                                              |
| ------------- | ---------------------------------------------------- |
| `Account`     | Where money lives (checking / savings / credit card) |
| `Category`    | Income or expense category                           |
| `Transaction` | A single income or expense entry                     |
| `Budget`      | A monthly spending limit for one category            |

See [`prisma/schema.prisma`](prisma/schema.prisma).

## Local development

### Option A — Docker Compose (app + database)

```bash
cd sample-app
docker compose up --build
```

- App: http://localhost:3000
- Postgres: `localhost:5433` (`finance` / `finance` / `finance`)

Migrations and seed data are applied automatically on startup.

### Option B — Run Next.js directly

Requires a local Postgres. Start just the database from Compose:

```bash
cd sample-app
docker compose up -d minions-4rmy-finance-db
cp .env.example .env      # DATABASE_URL points at localhost:5433
npm install
npm run build             # runs `prisma generate`
npx prisma migrate deploy # create tables
npx prisma db seed        # load sample data
npm run dev               # http://localhost:3000
```

## Deploying to Fly.io

First-time setup (creates the app + a dedicated Postgres, then deploys):

```bash
cd sample-app

# 1. Create the Fly app (must match the `app` name in fly.toml).
fly apps create your-finance-sample

# 2. Create and attach a Postgres database. This sets the DATABASE_URL secret.
fly postgres create --name your-finance-sample-db --region fra
fly postgres attach your-finance-sample-db --app your-finance-sample

# 3. Deploy. The release command runs `prisma migrate deploy && prisma db seed`.
fly deploy
```

Subsequent deploys are just `fly deploy`. The seed step is idempotent: reference
data (accounts, categories, budgets) is upserted and transactions are only
inserted when the table is empty, so redeploys won't duplicate data.

## Scripts

| Script          | Description                                    |
| --------------- | ---------------------------------------------- |
| `npm run dev`   | Next.js dev server                             |
| `npm run build` | `prisma generate` + `next build`               |
| `npm run start` | Start the production server                    |
| `npm run release` | `prisma migrate deploy` + `prisma db seed` (used by Fly) |
