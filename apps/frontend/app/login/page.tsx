import Link from "next/link";

import { LoginForm } from "./view";

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
        <p className="zen-subtitle">Use your allowlisted email to receive a secure magic login link.</p>
        {denied ? <p className="zen-error">This email is not allowlisted for dashboard access.</p> : null}
        <LoginForm nextPath={next} />
        <p className="zen-note" style={{ marginTop: 14 }}>
          After opening the magic link, you should be redirected to your dashboard.
        </p>
        <p className="zen-note" style={{ marginTop: 10 }}>
          <Link href="/">Back to home</Link>
        </p>
      </section>
    </main>
  );
}

