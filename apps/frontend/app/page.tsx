import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home",
};

export default function HomePage() {
  return (
    <main className="zen-home">
      <section className="zen-home-hero">
        <span className="zen-chip zen-stagger" style={{ animationDelay: "0ms" }}>
          Zen Daily Wisdom
        </span>
        <h1 className="zen-home-title zen-stagger" style={{ animationDelay: "80ms" }}>
          Calm daily reflections,
          <br />
          tuned for you.
        </h1>
        <p className="zen-home-lede zen-stagger" style={{ animationDelay: "160ms" }}>
          A short passage from public-domain wisdom — Stoic, Indian, Sufi, Zen, naturalist —
          and one grounded reflection, delivered to your inbox at dawn. Three quiet check-ins
          a day shape what tomorrow holds.
        </p>
        <div
          className="zen-home-cta-row zen-stagger"
          style={{ animationDelay: "240ms" }}
        >
          <Link className="zen-button" href="/dashboard">
            Open dashboard
          </Link>
          <Link className="zen-button zen-button-secondary" href="/login">
            Log in
          </Link>
        </div>
        <div
          className="zen-home-ornament zen-stagger"
          aria-hidden="true"
          style={{ animationDelay: "320ms" }}
        >
          <span className="zen-home-ornament-shape zen-home-ornament-clay" />
          <span className="zen-home-ornament-shape zen-home-ornament-dot" />
          <span className="zen-home-ornament-shape zen-home-ornament-pill" />
        </div>
      </section>

      <section
        className="zen-home-preview zen-stagger"
        style={{ animationDelay: "440ms" }}
        aria-label="A sample of what lands in your inbox"
      >
        <p className="zen-home-eyebrow">Sample reflection</p>
        <h2 className="zen-home-preview-theme">Theme: Patience</h2>
        <p className="zen-home-preview-thought">
          Pause for one steady breath before the day pulls you in every direction. The ridges
          abide. Let this line anchor one honest hour of focused work.
        </p>
        <p className="zen-home-preview-citation">— Marcus Aurelius, Meditations IV.18</p>
      </section>

      <section
        className="zen-home-meta zen-stagger"
        style={{ animationDelay: "540ms" }}
        aria-label="What this is"
      >
        <div className="zen-home-meta-grid">
          <div>
            <p className="zen-home-meta-label">What it is</p>
            <p className="zen-home-meta-body">
              A personal service that pairs public-domain wisdom with a generative reflection,
              tuned by your own check-in answers.
            </p>
          </div>
          <div>
            <p className="zen-home-meta-label">How it works</p>
            <p className="zen-home-meta-body">
              Retrieval over a hand-curated corpus, a Gemini Flash reflection grounded in one
              quoted passage, and a Mood Score from your three daily check-ins.
            </p>
          </div>
          <div>
            <p className="zen-home-meta-label">Who it&apos;s for</p>
            <p className="zen-home-meta-body">
              One person. Allowlisted access only. Email + Telegram delivery, free tier
              throughout, no monthly cost.
            </p>
          </div>
        </div>
      </section>

      <footer className="zen-home-footer">
        <p>Built privately, for one inbox. Corpus is public-domain English translations.</p>
      </footer>
    </main>
  );
}
