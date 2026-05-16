import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orange Model Demo",
  description: "Demo of Orange-trained prediction models",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <main className="mx-auto max-w-5xl px-4 py-10 sm:py-14">{children}</main>
      </body>
    </html>
  );
}
