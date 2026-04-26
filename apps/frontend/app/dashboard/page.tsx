import { SendNowButton } from "@/components/SendNowButton";
import { fetchBandit, fetchCheckins, fetchHealth, fetchHistory, fetchToday } from "@/lib/api";
import { createServerSupabaseClient } from "@/lib/supabase/server";

function styleLabel(styleKey?: string | null): string {
  switch (styleKey) {
    case "poetic_minimal":
      return "A - Poetic Minimal";
    case "practical_grounded":
      return "B - Practical Grounded";
    case "mixed_poetic_action":
      return "C - Mixed (Poetic + Action)";
    case "nature_seasons":
      return "D - Nature & Seasons";
    default:
      return "n/a";
  }
}

export default async function DashboardPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { session }
  } = await supabase.auth.getSession();
  const token = session?.access_token || "";

  const [healthResult, todayResult, historyResult, banditResult, checkinResult] = await Promise.allSettled([
    fetchHealth(),
    fetchToday(token),
    fetchHistory(token, 10),
    fetchBandit(token, 10),
    fetchCheckins(token, 30, 14)
  ]);

  const health = healthResult.status === "fulfilled" ? healthResult.value : null;
  const today = todayResult.status === "fulfilled" ? todayResult.value.data : null;
  const history = historyResult.status === "fulfilled" ? historyResult.value.data : [];
  const bandit = banditResult.status === "fulfilled" ? banditResult.value.data : [];
  const checkins = checkinResult.status === "fulfilled" ? checkinResult.value.data : [];
  const checkinStats = checkinResult.status === "fulfilled" ? checkinResult.value.stats : null;

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "48px 20px" }}>
      <h1 style={{ marginTop: 0 }}>Dashboard</h1>
      <p style={{ lineHeight: 1.6 }}>Live backend data is now wired into this page.</p>

      <section
        style={{
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          marginBottom: 16
        }}
      >
        <h2 style={{ marginTop: 0 }}>System Health</h2>
        <p style={{ margin: "8px 0" }}>
          Status: <strong>{health?.status ?? "unavailable"}</strong>
        </p>
        <p style={{ margin: "8px 0" }}>
          Supabase configured: <strong>{String(health?.checks?.supabase_configured ?? false)}</strong>
        </p>
        <p style={{ margin: "8px 0" }}>
          Gemini configured: <strong>{String(health?.checks?.gemini_configured ?? false)}</strong>
        </p>
        <SendNowButton accessToken={token} />
      </section>

      <section
        style={{
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          marginBottom: 16
        }}
      >
        <h2 style={{ marginTop: 0 }}>Today</h2>
        {today ? (
          <>
            <p style={{ margin: "8px 0" }}>
              Date: <strong>{today.sent_date}</strong>
            </p>
            <p style={{ margin: "8px 0" }}>
              Tradition: <strong>{today.arm_tradition ?? "n/a"}</strong>
            </p>
            <p style={{ margin: "8px 0" }}>
              Theme: <strong>{today.theme_of_day ?? "n/a"}</strong>
            </p>
            <p style={{ margin: "8px 0" }}>
              Style: <strong>{styleLabel(today.style_key)}</strong>
            </p>
            <p style={{ whiteSpace: "pre-line", lineHeight: 1.6 }}>{today.llm_output ?? ""}</p>
          </>
        ) : (
          <p>No message found for today yet.</p>
        )}
      </section>

      <section
        style={{
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          marginBottom: 16
        }}
      >
        <h2 style={{ marginTop: 0 }}>Check-ins (14 Days)</h2>
        <p style={{ margin: "8px 0" }}>
          Completion rate:{" "}
          <strong>{checkinStats ? `${(checkinStats.completion_rate * 100).toFixed(1)}%` : "n/a"}</strong>
        </p>
        <p style={{ margin: "8px 0" }}>
          Avg mood:{" "}
          <strong>
            {checkinStats?.avg_mood !== null && checkinStats?.avg_mood !== undefined
              ? checkinStats.avg_mood.toFixed(2)
              : "n/a"}
          </strong>
          {" / 5"}
        </p>
        <p style={{ margin: "8px 0" }}>
          Avg challenge load:{" "}
          <strong>
            {checkinStats?.avg_challenge !== null && checkinStats?.avg_challenge !== undefined
              ? checkinStats.avg_challenge.toFixed(2)
              : "n/a"}
          </strong>
          {" / 5"}
        </p>
        {checkins.length > 0 ? (
          <p style={{ margin: "8px 0", color: "#555" }}>
            Last check-in: {checkins[0]?.checkin_date} ({checkins[0]?.window})
          </p>
        ) : (
          <p style={{ margin: "8px 0", color: "#555" }}>No check-ins recorded yet.</p>
        )}
      </section>

      <section
        style={{
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          marginBottom: 16
        }}
      >
        <h2 style={{ marginTop: 0 }}>Recent History</h2>
        {history.length === 0 ? (
          <p>No recent history.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Date</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                    Tradition
                  </th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Tone</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Style</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                    Feedback
                  </th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}>
                    <td style={{ borderBottom: "1px solid #f0f0f0", padding: 8 }}>{item.sent_date}</td>
                    <td style={{ borderBottom: "1px solid #f0f0f0", padding: 8 }}>
                      {item.arm_tradition ?? "n/a"}
                    </td>
                    <td style={{ borderBottom: "1px solid #f0f0f0", padding: 8 }}>
                      {item.arm_tone ?? "n/a"}
                    </td>
                    <td style={{ borderBottom: "1px solid #f0f0f0", padding: 8 }}>
                      {styleLabel(item.style_key)}
                    </td>
                    <td style={{ borderBottom: "1px solid #f0f0f0", padding: 8 }}>
                      {(item.feedback ?? []).length > 0
                        ? (item.feedback ?? [])
                            .map((f) => `${f.rating ?? "?"} (${f.channel ?? "unknown"})`)
                            .join(", ")
                        : "No feedback"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section
        style={{
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16
        }}
      >
        <h2 style={{ marginTop: 0 }}>Bandit Arms (Top)</h2>
        {bandit.length === 0 ? (
          <p>No bandit state available yet. Add feedback to populate this.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {bandit.map((arm) => (
              <li key={arm.arm_key} style={{ marginBottom: 6 }}>
                <strong>{arm.arm_key}</strong> - expected value{" "}
                {Number(arm.expected_value ?? 0).toFixed(3)} ({arm.pulls ?? 0} pulls)
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

