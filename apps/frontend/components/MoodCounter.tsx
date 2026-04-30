"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  /** Target value to animate to. Pass `null` for "no data". */
  value: number | null;
  /** Suffix shown after the number, e.g. "/ 100". */
  suffix?: string;
  /** Animation duration in ms. */
  durationMs?: number;
  /** Decimals for the displayed number. 0 by default. */
  decimals?: number;
  /** Optional aria label override. */
  label?: string;
};

/**
 * Animated counter that eases from 0 (or its previous value) to `value`
 * over `durationMs`. Respects prefers-reduced-motion: under that setting
 * it snaps to the final value with no animation.
 */
export function MoodCounter({
  value,
  suffix,
  durationMs = 900,
  decimals = 0,
  label,
}: Props) {
  const [displayed, setDisplayed] = useState<number>(value ?? 0);
  const previousValueRef = useRef<number>(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (value === null) {
      setDisplayed(0);
      previousValueRef.current = 0;
      return;
    }
    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setDisplayed(value);
      previousValueRef.current = value;
      return;
    }
    const start = performance.now();
    const from = previousValueRef.current;
    const to = value;
    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const next = from + (to - from) * eased;
      setDisplayed(next);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        previousValueRef.current = to;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [value, durationMs]);

  if (value === null) {
    return (
      <span className="zen-counter zen-counter--empty" aria-label={label ?? "No data"}>
        —
      </span>
    );
  }

  const formatted = decimals > 0 ? displayed.toFixed(decimals) : Math.round(displayed).toString();
  return (
    <span className="zen-counter" aria-label={label ?? `${formatted}${suffix ?? ""}`}>
      <span className="zen-counter-value">{formatted}</span>
      {suffix ? <span className="zen-counter-suffix">{suffix}</span> : null}
    </span>
  );
}
