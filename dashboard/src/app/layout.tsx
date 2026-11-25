import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "RAGBench — 7-Config RAG Evaluation Dashboard",
  description: "Stage-by-stage RAG benchmark across 3 public documents and 60 golden questions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
