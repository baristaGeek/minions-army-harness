// Placeholder data. The Prisma models in prisma/schema.prisma are the real data
// source; this page renders static rows so `npm run build` stays deterministic and
// does not require a database.
const RECENT_TRANSACTIONS = [
  { id: "1", date: "2026-07-18", description: "Paycheck", category: "Salary", amount: 4200 },
  { id: "2", date: "2026-07-17", description: "Groceries", category: "Food", amount: -128.44 },
  { id: "3", date: "2026-07-15", description: "Electricity bill", category: "Utilities", amount: -86.1 },
  { id: "4", date: "2026-07-14", description: "Coffee", category: "Food", amount: -5.75 },
];

const SUMMARY = [
  { label: "Total balance", value: 12480.31 },
  { label: "Income this month", value: 4200 },
  { label: "Spent this month", value: 1320.29 },
];

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-10">
      <section className="grid gap-4 sm:grid-cols-3">
        {SUMMARY.map((item) => (
          <div
            key={item.label}
            className="rounded-lg border border-slate-200 p-4 dark:border-slate-800"
          >
            <p className="text-sm text-slate-500 dark:text-slate-400">{item.label}</p>
            <p className="mt-1 text-2xl font-semibold">{currency.format(item.value)}</p>
          </div>
        ))}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent transactions</h2>
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-800">
              <th className="py-2 font-medium">Date</th>
              <th className="py-2 font-medium">Description</th>
              <th className="py-2 font-medium">Category</th>
              <th className="py-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {RECENT_TRANSACTIONS.map((transaction) => (
              <tr
                key={transaction.id}
                className="border-b border-slate-100 last:border-0 dark:border-slate-900"
              >
                <td className="py-2 tabular-nums">{transaction.date}</td>
                <td className="py-2">{transaction.description}</td>
                <td className="py-2">{transaction.category}</td>
                <td className="py-2 text-right tabular-nums">
                  {currency.format(transaction.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
