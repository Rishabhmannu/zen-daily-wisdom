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
    <main style={{ maxWidth: 560, margin: "0 auto", padding: "48px 20px" }}>
      <h1 style={{ marginTop: 0 }}>Login</h1>
      <p style={{ lineHeight: 1.6 }}>Use your allowlisted email to receive a magic login link.</p>
      {denied ? (
        <p style={{ color: "#8a2f2f" }}>This email is not allowlisted for dashboard access.</p>
      ) : null}
      <LoginForm nextPath={next} />
      <p style={{ marginTop: 18, fontSize: 13, color: "#666" }}>
        After opening the magic link, you will be redirected to dashboard.
      </p>
      <p style={{ fontSize: 13 }}>
        <Link href="/">Back to home</Link>
      </p>
    </main>
  );
}

