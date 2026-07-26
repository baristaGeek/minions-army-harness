import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Sample App",
  description: "Sample app with a footer",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
        <footer>Sample app footer</footer>
      </body>
    </html>
  );
}
