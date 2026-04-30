import type { Metadata } from "next";
import { CheckinForm, type CheckinQuestion } from "./CheckinForm";

export const metadata: Metadata = {
  title: "Check-in",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<{ token?: string }>;
};

type ByTokenResponse = {
  status: string;
  window: "morning" | "midday" | "evening";
  date: string;
  questions: CheckinQuestion[];
  schema_version: number;
};

function backendUrl(): string {
  const raw = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  return raw.replace(/\/$/, "");
}

function windowTitle(window: string): string {
  return window.charAt(0).toUpperCase() + window.slice(1);
}

function prettyDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

async function fetchByToken(token: string): Promise<
  { ok: true; data: ByTokenResponse } | { ok: false; status: number; message: string }
> {
  const base = backendUrl();
  if (!base) {
    return { ok: false, status: 500, message: "NEXT_PUBLIC_BACKEND_URL is not configured." };
  }
  try {
    const response = await fetch(
      `${base}/checkin/by-token?token=${encodeURIComponent(token)}`,
      { cache: "no-store" }
    );
    if (!response.ok) {
      const text = await response.text();
      let message = text || `Request failed (${response.status})`;
      try {
        const payload = JSON.parse(text) as { detail?: string; error?: string };
        message = payload.detail || payload.error || message;
      } catch {
        // leave message as text
      }
      return { ok: false, status: response.status, message };
    }
    const data = (await response.json()) as ByTokenResponse;
    return { ok: true, data };
  } catch (error) {
    return {
      ok: false,
      status: 502,
      message: error instanceof Error ? error.message : "Could not reach backend.",
    };
  }
}

export default async function CheckinPage({ searchParams }: Props) {
  const params = await searchParams;
  const token = (params.token || "").trim();

  if (!token) {
    return (
      <main className="zen-shell zen-auth-shell zen-checkin-shell">
        <section className="zen-checkin-card">
          <span className="zen-chip">Zen Check-in</span>
          <h1 className="zen-checkin-title">Missing check-in link</h1>
          <p className="zen-checkin-lede">
            This page needs a signed check-in link. Open the latest check-in email and tap{" "}
            <strong>Begin Check-in</strong>.
          </p>
        </section>
      </main>
    );
  }

  const result = await fetchByToken(token);
  if (!result.ok) {
    return (
      <main className="zen-shell zen-auth-shell zen-checkin-shell">
        <section className="zen-checkin-card">
          <span className="zen-chip">Zen Check-in</span>
          <h1 className="zen-checkin-title">This link can&apos;t be used</h1>
          <p className="zen-checkin-lede">{result.message}</p>
          <p className="zen-note" style={{ marginTop: 12 }}>
            Check-in links are valid for 36 hours. If yours expired, the next reminder email will
            contain a fresh one.
          </p>
        </section>
      </main>
    );
  }

  const { window: windowName, date: checkinDate, questions } = result.data;

  return (
    <main className="zen-shell zen-checkin-shell">
      <section className="zen-checkin-card">
        <div className="zen-checkin-eyebrow-row">
          <span className="zen-chip">Zen Check-in</span>
          <span className="zen-checkin-meta">
            {windowTitle(windowName)} · {prettyDate(checkinDate)}
          </span>
        </div>
        <h1 className="zen-checkin-title">A 60-second pause</h1>
        <p className="zen-checkin-lede">
          {questions.length} quick question{questions.length === 1 ? "" : "s"} on a 1–5 scale.
          Your answers shape tomorrow&apos;s reflection. No login needed — this link is yours.
        </p>
        <CheckinForm
          token={token}
          questions={questions}
          window={windowName}
          checkinDate={checkinDate}
        />
      </section>
    </main>
  );
}
