"use client";

import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";

type Props = {
  nextPath: string;
};

export function LoginForm({ nextPath }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const [mode, setMode] = useState<"password" | "magic">("password");

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const queryError = search.get("error");
    if (queryError) {
      setError(decodeURIComponent(queryError.replace(/\+/g, " ")));
      return;
    }

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

  function isAllowlisted(targetEmail: string): boolean {
    const allowedRaw = process.env.NEXT_PUBLIC_ALLOWED_EMAILS || "";
    const allowed = new Set(
      allowedRaw
        .split(",")
        .map((entry) => entry.trim().toLowerCase())
        .filter(Boolean)
    );
    return !(allowed.size > 0 && !allowed.has(targetEmail.toLowerCase().trim()));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setStatus("");
    if (mode === "magic" && cooldownLeft > 0) {
      setError(`Please wait ${cooldownLeft}s before requesting another link.`);
      return;
    }

    try {
      if (!isAllowlisted(email)) {
        setError("This email is not allowlisted.");
        return;
      }

      const supabase = createClient();
      let signInError: Error | null = null;
      if (mode === "password") {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        signInError = error;
      } else {
        const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`;
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: {
            emailRedirectTo: redirectTo
          }
        });
        signInError = error;
      }

      if (signInError) {
        const msg = signInError.message || "Failed to send magic link.";
        setError(msg);
        if (mode === "magic") {
          const match = msg.match(/after\s+(\d+)\s+seconds?/i);
          if (match?.[1]) {
            const seconds = Number.parseInt(match[1], 10);
            if (Number.isFinite(seconds) && seconds > 0) {
              setCooldownLeft(seconds);
            }
          }
        }
        return;
      }
      if (mode === "password") {
        window.location.assign(nextPath);
        return;
      }
      setStatus("Check your email for the magic link.");
      setCooldownLeft(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    }
  }

  async function onCreateAccount() {
    setError("");
    setStatus("");
    if (!isAllowlisted(email)) {
      setError("This email is not allowlisted.");
      return;
    }
    if (!password || password.length < 8) {
      setError("Use a password with at least 8 characters.");
      return;
    }
    const supabase = createClient();
    const { error: signUpError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
      },
    });
    if (signUpError) {
      setError(signUpError.message || "Could not create account.");
      return;
    }
    setStatus("Account created. Use password login now or verify via email if prompted.");
  }

  return (
    <form onSubmit={onSubmit} className="zen-grid" style={{ marginTop: 10 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className={`zen-button ${mode === "password" ? "" : "zen-button-secondary"}`}
          onClick={() => setMode("password")}
        >
          Password login
        </button>
        <button
          type="button"
          className={`zen-button ${mode === "magic" ? "" : "zen-button-secondary"}`}
          onClick={() => setMode("magic")}
        >
          Magic link
        </button>
      </div>
      <input
        type="email"
        required
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="zen-input"
      />
      {mode === "password" ? (
        <input
          type="password"
          required
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="zen-input"
        />
      ) : null}
      <button
        type="submit"
        disabled={mode === "magic" && cooldownLeft > 0}
        className="zen-button"
      >
        {mode === "magic"
          ? cooldownLeft > 0
            ? `Wait ${cooldownLeft}s`
            : "Send magic link"
          : "Sign in"}
      </button>
      {mode === "password" ? (
        <button type="button" className="zen-button zen-button-secondary" onClick={onCreateAccount}>
          Create account
        </button>
      ) : null}
      {status ? <p className="zen-success">{status}</p> : null}
      {error ? <p className="zen-error">{error}</p> : null}
    </form>
  );
}

