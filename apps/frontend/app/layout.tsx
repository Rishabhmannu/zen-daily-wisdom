import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Zen Daily Wisdom",
  description: "Personalized daily wisdom dashboard"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          background: "#FAF7F2",
          color: "#2E4A3C",
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
        }}
      >
        {children}
      </body>
    </html>
  );
}

