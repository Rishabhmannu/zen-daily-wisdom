import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home",
};

export default function HomePage() {
  return (
    <main className="zen-shell">
      <section className="zen-card">
        <span className="zen-chip">Zen Daily Wisdom</span>
        <h1 className="zen-title">Calm daily reflections, tuned for you.</h1>
        <p className="zen-subtitle">
          Open your dashboard to track daily thoughts, style feedback, check-ins, and delivery health across
          Gmail and Telegram.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link className="zen-button" href="/login">
            Login
          </Link>
          <Link className="zen-button" href="/dashboard">
            Open dashboard
          </Link>
        </div>
      </section>
    </main>
  );
}

