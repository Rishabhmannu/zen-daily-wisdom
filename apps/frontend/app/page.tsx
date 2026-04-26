import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "48px 20px" }}>
      <h1 style={{ marginTop: 0 }}>Zen Daily Wisdom</h1>
      <p style={{ lineHeight: 1.6 }}>
        Frontend scaffold is ready. Next steps are wiring Supabase auth and dashboard data fetches.
      </p>
      <ul>
        <li>
          <Link href="/login">Login</Link>
        </li>
        <li>
          <Link href="/dashboard">Dashboard</Link>
        </li>
      </ul>
    </main>
  );
}

