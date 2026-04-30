"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  /** 0..1 fraction. */
  value: number | null;
  /** Outer diameter in px. */
  size?: number;
  /** Stroke width in px. */
  strokeWidth?: number;
  /** Animation duration in ms. */
  durationMs?: number;
};

/**
 * Animated SVG ring that fills from 0 to `value` over `durationMs`.
 * Respects prefers-reduced-motion. Renders a quiet "—" placeholder when
 * value is null (no submissions yet).
 */
export function CompletionRing({
  value,
  size = 96,
  strokeWidth = 9,
  durationMs = 900,
}: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const target = value === null ? 0 : Math.max(0, Math.min(1, value));

  const [progress, setProgress] = useState<number>(0);
  const previousRef = useRef<number>(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (value === null) {
      setProgress(0);
      previousRef.current = 0;
      return;
    }
    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setProgress(target);
      previousRef.current = target;
      return;
    }
    const start = performance.now();
    const from = previousRef.current;
    const to = target;
    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setProgress(from + (to - from) * eased);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        previousRef.current = to;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [value, target, durationMs]);

  const offset = circumference * (1 - progress);
  const percentLabel =
    value === null ? "—" : `${Math.round(progress * 100)}%`;

  return (
    <div
      className="zen-ring"
      role="img"
      aria-label={`Check-in completion ${percentLabel}`}
    >
      <svg
        className="zen-ring-svg"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
      >
        <circle
          className="zen-ring-track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          className="zen-ring-progress"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="zen-ring-label">
        <span className="zen-ring-value">{percentLabel}</span>
      </div>
    </div>
  );
}
