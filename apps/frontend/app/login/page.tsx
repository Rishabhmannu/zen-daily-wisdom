import Link from "next/link";
import type { Metadata } from "next";

import { LoginForm } from "./view";

export const metadata: Metadata = {
  title: "Login",
};

type Props = {
  searchParams: Promise<{ next?: string; denied?: string }>;
};

export default async function LoginPage({ searchParams }: Props) {
  const params = await searchParams;
  const next = params.next || "/dashboard";
  const denied = params.denied === "1";

  return (
    <main className="zen-shell zen-auth-shell">
      <section className="zen-card">
        <h1 className="zen-title">Login</h1>
        <p className="zen-subtitle">
          Use password login for daily use (recommended). Magic links remain available as fallback.
        </p>
        {denied ? <p className="zen-error">This email is not allowlisted for dashboard access.</p> : null}
        <LoginForm nextPath={next} />
        <p className="zen-note" style={{ marginTop: 14 }}>
          For first-time setup, create accounts only for your allowlisted emails.
        </p>
        <p className="zen-note" style={{ marginTop: 10 }}>
          <Link href="/">Back to home</Link>
        </p>
      </section>
    </main>
  );
}

