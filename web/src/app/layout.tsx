import type { Metadata } from "next";
import "./globals.css";
import { DataProvider } from "@/lib/DataProvider";
import { BeginnerModeProvider } from "@/lib/BeginnerModeContext";

export const metadata: Metadata = {
  title: "SPHEREx Sky Diary — Solar System Mover Tracking",
  description:
    "Time-resolved infrared sky maps and automatic moving object detection from NASA's SPHEREx mission (NASA Space Apps Challenge 2026).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-space-deep text-apptext-primary min-h-screen">
        <DataProvider>
          <BeginnerModeProvider>
            {children}
          </BeginnerModeProvider>
        </DataProvider>
      </body>
    </html>
  );
}
