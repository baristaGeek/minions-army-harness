import { PrismaClient, Prisma } from "@prisma/client";

const prisma = new PrismaClient();

// Reference data -------------------------------------------------------------

const accounts = [
  { name: "Everyday Checking", type: "checking" },
  { name: "Rainy Day Savings", type: "savings" },
  { name: "Travel Rewards Card", type: "credit_card" },
  { name: "Cash Wallet", type: "checking" },
];

const categories = [
  { name: "Salary", type: "income" },
  { name: "Freelance", type: "income" },
  { name: "Interest", type: "income" },
  { name: "Groceries", type: "expense" },
  { name: "Rent", type: "expense" },
  { name: "Utilities", type: "expense" },
  { name: "Dining Out", type: "expense" },
  { name: "Transport", type: "expense" },
  { name: "Entertainment", type: "expense" },
  { name: "Health", type: "expense" },
];

// Monthly budgets keyed by category name.
const budgets: Record<string, number> = {
  Groceries: 500,
  "Dining Out": 200,
  Transport: 150,
  Entertainment: 120,
  Utilities: 250,
  Health: 100,
};

// Deterministic sample transactions ------------------------------------------

type SeedTxn = {
  description: string;
  amount: number;
  type: "income" | "expense";
  account: string;
  category: string;
  daysAgo: number;
};

const transactions: SeedTxn[] = [
  // Income
  { description: "Monthly salary", amount: 4200, type: "income", account: "Everyday Checking", category: "Salary", daysAgo: 45 },
  { description: "Monthly salary", amount: 4200, type: "income", account: "Everyday Checking", category: "Salary", daysAgo: 15 },
  { description: "Website project", amount: 950, type: "income", account: "Everyday Checking", category: "Freelance", daysAgo: 22 },
  { description: "Logo design gig", amount: 400, type: "income", account: "Everyday Checking", category: "Freelance", daysAgo: 6 },
  { description: "Savings interest", amount: 18.42, type: "income", account: "Rainy Day Savings", category: "Interest", daysAgo: 30 },

  // Rent & utilities
  { description: "Apartment rent", amount: 1500, type: "expense", account: "Everyday Checking", category: "Rent", daysAgo: 44 },
  { description: "Apartment rent", amount: 1500, type: "expense", account: "Everyday Checking", category: "Rent", daysAgo: 14 },
  { description: "Electricity bill", amount: 88.3, type: "expense", account: "Everyday Checking", category: "Utilities", daysAgo: 40 },
  { description: "Internet bill", amount: 59.99, type: "expense", account: "Everyday Checking", category: "Utilities", daysAgo: 12 },
  { description: "Water bill", amount: 34.5, type: "expense", account: "Everyday Checking", category: "Utilities", daysAgo: 11 },

  // Groceries
  { description: "Weekly groceries", amount: 112.44, type: "expense", account: "Travel Rewards Card", category: "Groceries", daysAgo: 38 },
  { description: "Weekly groceries", amount: 96.18, type: "expense", account: "Travel Rewards Card", category: "Groceries", daysAgo: 31 },
  { description: "Weekly groceries", amount: 134.72, type: "expense", account: "Travel Rewards Card", category: "Groceries", daysAgo: 24 },
  { description: "Weekly groceries", amount: 88.05, type: "expense", account: "Travel Rewards Card", category: "Groceries", daysAgo: 17 },
  { description: "Weekly groceries", amount: 121.9, type: "expense", account: "Travel Rewards Card", category: "Groceries", daysAgo: 9 },
  { description: "Weekly groceries", amount: 76.33, type: "expense", account: "Travel Rewards Card", category: "Groceries", daysAgo: 2 },

  // Dining
  { description: "Sushi dinner", amount: 62.5, type: "expense", account: "Travel Rewards Card", category: "Dining Out", daysAgo: 35 },
  { description: "Coffee & bagel", amount: 9.75, type: "expense", account: "Cash Wallet", category: "Dining Out", daysAgo: 21 },
  { description: "Pizza night", amount: 28.4, type: "expense", account: "Travel Rewards Card", category: "Dining Out", daysAgo: 8 },
  { description: "Brunch with friends", amount: 41.2, type: "expense", account: "Travel Rewards Card", category: "Dining Out", daysAgo: 3 },

  // Transport
  { description: "Metro pass", amount: 75, type: "expense", account: "Everyday Checking", category: "Transport", daysAgo: 33 },
  { description: "Ride share", amount: 18.6, type: "expense", account: "Travel Rewards Card", category: "Transport", daysAgo: 19 },
  { description: "Gas fill-up", amount: 52.11, type: "expense", account: "Travel Rewards Card", category: "Transport", daysAgo: 5 },

  // Entertainment
  { description: "Streaming subscription", amount: 15.99, type: "expense", account: "Everyday Checking", category: "Entertainment", daysAgo: 29 },
  { description: "Concert tickets", amount: 89, type: "expense", account: "Travel Rewards Card", category: "Entertainment", daysAgo: 16 },
  { description: "Movie night", amount: 24, type: "expense", account: "Cash Wallet", category: "Entertainment", daysAgo: 4 },

  // Health
  { description: "Pharmacy", amount: 27.85, type: "expense", account: "Cash Wallet", category: "Health", daysAgo: 26 },
  { description: "Gym membership", amount: 45, type: "expense", account: "Everyday Checking", category: "Health", daysAgo: 13 },
];

function dateDaysAgo(days: number): Date {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() - days);
  return d;
}

async function main() {
  // Upsert reference data (idempotent by unique name).
  const accountByName = new Map<string, string>();
  for (const a of accounts) {
    const rec = await prisma.account.upsert({
      where: { name: a.name },
      update: { type: a.type },
      create: a,
    });
    accountByName.set(a.name, rec.id);
  }

  const categoryByName = new Map<string, string>();
  for (const c of categories) {
    const rec = await prisma.category.upsert({
      where: { name: c.name },
      update: { type: c.type },
      create: c,
    });
    categoryByName.set(c.name, rec.id);
  }

  // Upsert budgets (idempotent by unique categoryId).
  for (const [categoryName, amount] of Object.entries(budgets)) {
    const categoryId = categoryByName.get(categoryName);
    if (!categoryId) continue;
    await prisma.budget.upsert({
      where: { categoryId },
      update: { amount: new Prisma.Decimal(amount) },
      create: { categoryId, amount: new Prisma.Decimal(amount) },
    });
  }

  // Only seed transactions when none exist, so redeploys don't duplicate them.
  const existing = await prisma.transaction.count();
  if (existing === 0) {
    for (const t of transactions) {
      const accountId = accountByName.get(t.account);
      const categoryId = categoryByName.get(t.category);
      if (!accountId || !categoryId) continue;
      await prisma.transaction.create({
        data: {
          description: t.description,
          amount: new Prisma.Decimal(t.amount),
          type: t.type,
          date: dateDaysAgo(t.daysAgo),
          accountId,
          categoryId,
        },
      });
    }
    console.log(`Seeded ${transactions.length} transactions.`);
  } else {
    console.log(`Transactions already present (${existing}); skipping transaction seed.`);
  }

  console.log("Seed complete.");
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
