import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "La Longue Marche — Review",
  description:
    "Side-by-side review of LLM transcriptions of Grothendieck manuscripts.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <a href="/" className="site-title">
            La Longue Marche <span className="site-title-sub">— transcription review</span>
          </a>
          <a href="/api/logout" className="header-link">
            Log out
          </a>
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
