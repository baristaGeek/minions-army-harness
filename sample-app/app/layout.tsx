import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "M1N10NS 4RMY F1N4NC3 4PP",
  description: "Personal finance tracker used as the sample target app for coding agents.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-6">
          <header className="border-b border-slate-200 py-6 dark:border-slate-800">
            <h1 className="text-xl font-semibold tracking-tight">M1N10NS 4RMY F1N4NC3 4PP</h1>
          </header>
          <main className="flex-1 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
