"use client";

import { useMemo, useState } from "react";

export type CheckinQuestion = {
  key: string;
  label: string;
  scale: [number, number];
};

type Props = {
  token: string;
  questions: CheckinQuestion[];
  window: "morning" | "midday" | "evening";
  checkinDate: string;
};

const SCALE_HINTS: Record<number, string> = {
  1: "Not at all",
  2: "A little",
  3: "Somewhat",
  4: "Quite a bit",
  5: "Very much",
};

function backendUrl(): string {
  const raw = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  return raw.replace(/\/$/, "");
}

type ResponsePassage = {
  text: string;
  source: string;
  citation: string;
  tradition: string;
};

type ResponseBundle = {
  message?: string;
  message_source?: string;
  passage?: ResponsePassage | null;
  passage_source?: string;
};

export function CheckinForm({ token, questions, window, checkinDate }: Props) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [note, setNote] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitted, setSubmitted] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [moodScore, setMoodScore] = useState<number | null>(null);
  const [responseBundle, setResponseBundle] = useState<ResponseBundle | null>(null);

  const totalQuestions = questions.length;
  const answeredCount = useMemo(
    () => questions.filter((q) => typeof answers[q.key] === "number").length,
    [questions, answers]
  );
  const allAnswered = answeredCount === totalQuestions;
  const progressPct = totalQuestions === 0 ? 0 : Math.round((answeredCount / totalQuestions) * 100);

  const setAnswer = (key: string, score: number) => {
    setAnswers((prev) => ({ ...prev, [key]: score }));
  };

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!allAnswered || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const base = backendUrl();
      if (!base) {
        throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured.");
      }
      const payload = {
        token,
        channel: "email" as const,
        note: note.trim() ? note.trim() : null,
        answers: questions.map((q) => ({ key: q.key, score: answers[q.key] })),
      };
      const response = await fetch(`${base}/checkin/submit-by-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const text = await response.text();
        let message = text || `Submit failed (${response.status})`;
        try {
          const errPayload = JSON.parse(text) as { detail?: string; error?: string };
          message = errPayload.detail || errPayload.error || message;
        } catch {
          // keep raw text as message
        }
        throw new Error(message);
      }
      const result = (await response.json()) as {
        scores?: { mood_score_weighted?: number | null };
        response?: ResponseBundle;
      };
      const score = result.scores?.mood_score_weighted ?? null;
      setMoodScore(typeof score === "number" ? score : null);
      setResponseBundle(result.response ?? null);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit check-in.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    const score = moodScore !== null ? Math.round(moodScore) : null;
    const band =
      score === null
        ? null
        : score >= 75
          ? "steady and clear"
          : score >= 55
            ? "moving along"
            : score >= 35
              ? "carrying weight"
              : "gentle with yourself today";
    const observation = responseBundle?.message?.trim() || null;
    const passage = responseBundle?.passage ?? null;
    const passageHasText = passage && passage.text && passage.text.trim().length > 0;
    return (
      <div className="zen-checkin-thanks">
        <h2 className="zen-checkin-thanks-title zen-stagger" style={{ animationDelay: "0ms" }}>
          Saved. Thank you.
        </h2>
        {score !== null ? (
          <div
            className="zen-mood-pill zen-stagger"
            aria-live="polite"
            style={{ animationDelay: "80ms" }}
          >
            <span className="zen-mood-pill-label">Mood</span>
            <span className="zen-mood-pill-value">{score}</span>
            <span className="zen-mood-pill-suffix">/ 100</span>
            {band ? <span className="zen-mood-pill-band">· {band}</span> : null}
          </div>
        ) : null}
        {observation ? (
          <blockquote
            className="zen-observation zen-stagger"
            aria-label="Reflection from your check-in"
            style={{ animationDelay: "180ms" }}
          >
            <p className="zen-observation-text">{observation}</p>
          </blockquote>
        ) : null}
        {passageHasText ? (
          <figure
            className="zen-passage-card zen-stagger"
            aria-label="A passage from the corpus"
            style={{ animationDelay: "280ms" }}
          >
            <p className="zen-passage-eyebrow">Passage for this hour</p>
            <p className="zen-passage-text">{passage!.text}</p>
            <figcaption className="zen-passage-citation">
              — {passage!.source ? passage!.source : "Unknown source"}
              {passage!.citation ? `, ${passage!.citation}` : ""}
            </figcaption>
          </figure>
        ) : null}
        <p className="zen-checkin-lede zen-stagger" style={{ marginBottom: 8, animationDelay: "360ms" }}>
          Your {window} check-in for {checkinDate} has been recorded. Tomorrow&apos;s reflection
          will lean on what you said.
        </p>
        <p className="zen-note zen-stagger" style={{ animationDelay: "440ms" }}>
          You can close this tab.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="zen-checkin-form" noValidate>
      <div className="zen-progress" aria-hidden="true">
        <div className="zen-progress-track">
          <div className="zen-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <span className="zen-progress-label">
          {answeredCount} / {totalQuestions} answered
        </span>
      </div>

      <ol className="zen-checkin-list">
        {questions.map((question, index) => {
          const current = answers[question.key];
          return (
            <li key={question.key} className="zen-checkin-question">
              <div className="zen-checkin-question-head">
                <span className="zen-checkin-question-index">{index + 1}</span>
                <p className="zen-checkin-question-label">{question.label}</p>
              </div>
              <div
                className="zen-rating-row"
                role="radiogroup"
                aria-label={question.label}
              >
                {[1, 2, 3, 4, 5].map((score) => {
                  const isActive = current === score;
                  return (
                    <button
                      key={score}
                      type="button"
                      role="radio"
                      aria-checked={isActive}
                      className={`zen-rating-btn${isActive ? " zen-rating-btn--active" : ""}`}
                      onClick={() => setAnswer(question.key, score)}
                    >
                      <span className="zen-rating-btn-score">{score}</span>
                      <span className="zen-rating-btn-hint">{SCALE_HINTS[score]}</span>
                    </button>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="zen-checkin-note">
        <label htmlFor="checkin-note" className="zen-checkin-note-label">
          Anything else worth noting? <span className="zen-checkin-note-optional">(optional)</span>
        </label>
        <textarea
          id="checkin-note"
          className="zen-checkin-note-input"
          rows={3}
          maxLength={800}
          placeholder="One sentence is enough."
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>

      {error ? (
        <p className="zen-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="zen-checkin-submit-row">
        <button
          type="submit"
          className="zen-button zen-checkin-submit"
          disabled={!allAnswered || submitting}
        >
          {submitting ? "Saving…" : allAnswered ? "Submit Check-in" : `Answer all ${totalQuestions} to submit`}
        </button>
        <span className="zen-note zen-checkin-meta-line">
          {windowMeta(window)} · {checkinDate}
        </span>
      </div>
    </form>
  );
}

function windowMeta(window: "morning" | "midday" | "evening"): string {
  if (window === "morning") return "Morning check-in";
  if (window === "midday") return "Midday check-in";
  return "Evening check-in";
}
