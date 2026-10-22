import type { Metadata } from "next";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "HireMatch — Recruitment Screening & Analytics",
  description: "Human-centered candidate screening and evaluation platform. Thoughtful scoring, transparent evidence, recruiter-in-the-loop.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-stone-50 font-sans antialiased text-charcoal-900">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
