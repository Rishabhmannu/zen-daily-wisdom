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
    <main className="zen-shell">
      <section className="zen-card">
        <span className="zen-chip">Dashboard</span>
        <h1 className="zen-title">Your daily wisdom control center</h1>
        <p className="zen-subtitle">
          Track today&apos;s message quality, check-in completion, style performance, and send status in one
          place.
        </p>
      </section>

      <section className="zen-card">
        <h2 className="zen-section-title">System Health</h2>
        <p className="zen-row">
          Status: <strong>{health?.status ?? "unavailable"}</strong>
        </p>
        <p className="zen-row">
          Supabase configured: <strong>{String(health?.checks?.supabase_configured ?? false)}</strong>
        </p>
        <p className="zen-row">
          Gemini configured: <strong>{String(health?.checks?.gemini_configured ?? false)}</strong>
        </p>
        <SendNowButton accessToken={token} />
      </section>

      <section className="zen-card">
        <h2 className="zen-section-title">Today</h2>
        {today ? (
          <>
            <p className="zen-row">
              Date: <strong>{today.sent_date}</strong>
            </p>
            <p className="zen-row">
              Tradition: <strong>{today.arm_tradition ?? "n/a"}</strong>
            </p>
            <p className="zen-row">
              Theme: <strong>{today.theme_of_day ?? "n/a"}</strong>
            </p>
            <p className="zen-row">
              Style: <strong>{styleLabel(today.style_key)}</strong>
            </p>
            <p className="zen-subtitle" style={{ marginBottom: 0, whiteSpace: "pre-line" }}>
              {today.llm_output ?? ""}
            </p>
          </>
        ) : (
          <p className="zen-note">No message found for today yet.</p>
        )}
      </section>

      <section className="zen-card">
        <h2 className="zen-section-title">Check-ins (14 Days)</h2>
        <p className="zen-row">
          Completion rate:{" "}
          <strong>{checkinStats ? `${(checkinStats.completion_rate * 100).toFixed(1)}%` : "n/a"}</strong>
        </p>
        <p className="zen-row">
          Avg mood:{" "}
          <strong>
            {checkinStats?.avg_mood !== null && checkinStats?.avg_mood !== undefined
              ? checkinStats.avg_mood.toFixed(2)
              : "n/a"}
          </strong>
          {" / 5"}
        </p>
        <p className="zen-row">
          Avg challenge load:{" "}
          <strong>
            {checkinStats?.avg_challenge !== null && checkinStats?.avg_challenge !== undefined
              ? checkinStats.avg_challenge.toFixed(2)
              : "n/a"}
          </strong>
          {" / 5"}
        </p>
        {checkins.length > 0 ? (
          <p className="zen-note">
            Last check-in: {checkins[0]?.checkin_date} ({checkins[0]?.window})
          </p>
        ) : (
          <p className="zen-note">No check-ins recorded yet.</p>
        )}
      </section>

      <section className="zen-card">
        <h2 className="zen-section-title">Recent History</h2>
        {history.length === 0 ? (
          <p className="zen-note">No recent history.</p>
        ) : (
          <div className="zen-table-wrap">
            <table className="zen-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Tradition</th>
                  <th>Tone</th>
                  <th>Style</th>
                  <th>Feedback</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}>
                    <td>{item.sent_date}</td>
                    <td>{item.arm_tradition ?? "n/a"}</td>
                    <td>{item.arm_tone ?? "n/a"}</td>
                    <td>{styleLabel(item.style_key)}</td>
                    <td>
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

      <section className="zen-card">
        <h2 className="zen-section-title">Bandit Arms (Top)</h2>
        {bandit.length === 0 ? (
          <p className="zen-note">No bandit state available yet. Add feedback to populate this.</p>
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

