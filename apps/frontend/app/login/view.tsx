"use client";

import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";

type Props = {
  nextPath: string;
};

export function LoginForm({ nextPath }: Props) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [cooldownLeft, setCooldownLeft] = useState(0);

  useEffect(() => {
    const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
    if (!hash) {
      return;
    }
    const params = new URLSearchParams(hash);
    const description = params.get("error_description");
    const errorCode = params.get("error_code");
    if (description) {
      setError(decodeURIComponent(description.replace(/\+/g, " ")));
    } else if (errorCode) {
      setError(`Login failed (${errorCode}). Please request a new magic link.`);
    }
  }, []);

  useEffect(() => {
    if (cooldownLeft <= 0) {
      return;
    }
    const timer = window.setInterval(() => {
      setCooldownLeft((value) => (value > 0 ? value - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [cooldownLeft]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setStatus("");
    if (cooldownLeft > 0) {
      setError(`Please wait ${cooldownLeft}s before requesting another link.`);
      return;
    }

    try {
      const allowedRaw = process.env.NEXT_PUBLIC_ALLOWED_EMAILS || "";
      const allowed = new Set(
        allowedRaw
          .split(",")
          .map((entry) => entry.trim().toLowerCase())
          .filter(Boolean)
      );
      if (allowed.size > 0 && !allowed.has(email.toLowerCase().trim())) {
        setError("This email is not allowlisted.");
        return;
      }

      const supabase = createClient();
      const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`;
      const { error: signInError } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: redirectTo
        }
      });
      if (signInError) {
        const msg = signInError.message || "Failed to send magic link.";
        setError(msg);
        const match = msg.match(/after\s+(\d+)\s+seconds?/i);
        if (match?.[1]) {
          const seconds = Number.parseInt(match[1], 10);
          if (Number.isFinite(seconds) && seconds > 0) {
            setCooldownLeft(seconds);
          }
        }
        return;
      }
      setStatus("Check your email for the magic link.");
      setCooldownLeft(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send magic link.");
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 10, marginTop: 16 }}>
      <input
        type="email"
        required
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #ddd" }}
      />
      <button
        type="submit"
        disabled={cooldownLeft > 0}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid #222",
          opacity: cooldownLeft > 0 ? 0.6 : 1,
          cursor: cooldownLeft > 0 ? "not-allowed" : "pointer"
        }}
      >
        {cooldownLeft > 0 ? `Wait ${cooldownLeft}s` : "Send magic link"}
      </button>
      {status ? <p style={{ margin: 0, color: "#225f32" }}>{status}</p> : null}
      {error ? <p style={{ margin: 0, color: "#8a2f2f" }}>{error}</p> : null}
    </form>
  );
}

