import type { Metadata } from "next";
import { Syne } from "next/font/google";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  weight: ["700", "800"],
  variable: "--font-syne",
});

export const metadata: Metadata = {
  title: "Loudrr - Earn Karma by Engaging",
  description: "Loudrr is a karma-based attention marketplace. Earn karma by engaging with posts. Spend karma to get engagement on yours.",
  openGraph: {
    title: "Loudrr - Earn Karma by Engaging",
    description: "Join the waitlist for Loudrr - a karma-based attention marketplace.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={syne.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
