import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "Kairos — Ambient Action Extraction & Execution Engine",
  description: "Transform unstructured meeting transcripts, emails, and Slack threads into real verified side effects across Notion, Jira, Calendar, and Task Ledger via MCP.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <Navbar />
        <main style={{ flex: 1, padding: "2rem 0 4rem" }}>
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
