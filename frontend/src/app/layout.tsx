import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Kairos — Ambient Action Engine",
  description:
    "Turn unstructured conversations into executed actions across Notion, Jira, Calendar, and the Task Ledger — with human approval at every step.",
  icons: { icon: [{ url: "/favicon.ico" }, { url: "/icon.svg", type: "image/svg+xml" }] },
};

export const viewport: Viewport = {
  themeColor: "#09090b",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable}`}>
      <body style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <a
          href="#main-content"
          className="skip-link"
          style={{
            position: "absolute",
            left: "-9999px",
            top: "8px",
            zIndex: 100,
            padding: "8px 14px",
            background: "var(--bg-raised)",
            color: "var(--text)",
            borderRadius: "var(--r-sm)",
          }}
          onFocus={(e) => {
            (e.target as HTMLAnchorElement).style.left = "8px";
          }}
          onBlur={(e) => {
            (e.target as HTMLAnchorElement).style.left = "-9999px";
          }}
        >
          Skip to content
        </a>
        <Navbar />
        <main id="main-content" style={{ flex: 1, width: "100%", padding: "48px 0 64px" }}>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
