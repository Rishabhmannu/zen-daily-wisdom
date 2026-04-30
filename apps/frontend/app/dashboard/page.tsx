import { CompletionRing } from "@/components/CompletionRing";
import { LogoutButton } from "@/components/LogoutButton";
import { MoodCounter } from "@/components/MoodCounter";
import { MoodLineChart } from "@/components/MoodLineChart";
import { SendNowButton } from "@/components/SendNowButton";
import { WeeklyNarrative } from "@/components/WeeklyNarrative";
import {
  fetchBandit,
  fetchCheckins,
  fetchHealth,
  fetchHistory,
  fetchNarrative,
  fetchToday,
} from "@/lib/api";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
};

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

  const [
    healthResult,
    todayResult,
    historyResult,
    banditResult,
    checkinResult,
    narrativeResult,
  ] = await Promise.allSettled([
    fetchHealth(),
    fetchToday(token),
    fetchHistory(token, 10),
    fetchBandit(token, 10),
    fetchCheckins(token, 30, 14),
    fetchNarrative(token),
  ]);

  const health = healthResult.status === "fulfilled" ? healthResult.value : null;
  const today = todayResult.status === "fulfilled" ? todayResult.value.data : null;
  const history = historyResult.status === "fulfilled" ? historyResult.value.data : [];
  const bandit = banditResult.status === "fulfilled" ? banditResult.value.data : [];
  const checkins = checkinResult.status === "fulfilled" ? checkinResult.value.data : [];
  const checkinStats = checkinResult.status === "fulfilled" ? checkinResult.value.stats : null;
  const narrative = narrativeResult.status === "fulfilled" ? narrativeResult.value.data : null;

  return (
    <main className="zen-shell">
      <section className="zen-card">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <span className="zen-chip">Dashboard</span>
          <LogoutButton />
        </div>
        <h1 className="zen-title">Your daily wisdom control center</h1>
        <p className="zen-subtitle">
          Track today&apos;s message quality, check-in completion, style performance, and send status in one
          place.
        </p>
      </section>

      <WeeklyNarrative initial={narrative} accessToken={token} />

      <section className="zen-split">
        <h2 className="zen-split-title">User Experience</h2>

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

        <section className="zen-card zen-stats-card">
          <div className="zen-stats-head">
            <h2 className="zen-section-title" style={{ marginBottom: 0 }}>
              Check-ins (Last 14 Days)
            </h2>
            {checkins.length > 0 ? (
              <span className="zen-stats-meta">
                Last: {checkins[0]?.checkin_date} ({checkins[0]?.window})
              </span>
            ) : null}
          </div>

          <div className="zen-stats-grid">
            <div className="zen-stats-tile zen-stagger" style={{ animationDelay: "0ms" }}>
              <span className="zen-stats-tile-label">Completion</span>
              <CompletionRing
                value={checkinStats ? checkinStats.completion_rate : null}
              />
              <span className="zen-stats-tile-foot">
                of {checkinStats?.days_considered ?? 14} × 3 windows
              </span>
            </div>

            <div className="zen-stats-tile zen-stagger" style={{ animationDelay: "100ms" }}>
              <span className="zen-stats-tile-label">Avg Mood</span>
              <MoodCounter
                value={checkinStats?.avg_mood_0_100 ?? null}
                suffix=" / 100"
                label="Average mood over 14 days"
              />
              <span className="zen-stats-tile-foot">across all submissions</span>
            </div>

            <div className="zen-stats-tile zen-stagger" style={{ animationDelay: "200ms" }}>
              <span className="zen-stats-tile-label">Challenge Load</span>
              <MoodCounter
                value={checkinStats?.avg_challenge ?? null}
                suffix=" / 5"
                decimals={1}
                label="Average challenge load over 14 days"
              />
              <span className="zen-stats-tile-foot">5 = heaviest</span>
            </div>
          </div>

          <div className="zen-stagger" style={{ animationDelay: "320ms", marginTop: 14 }}>
            <p className="zen-stats-chart-label">Mood trend</p>
            <MoodLineChart series={checkinStats?.daily_series ?? []} />
          </div>

          {checkins.length === 0 ? (
            <p className="zen-note" style={{ marginTop: 12 }}>
              No check-ins recorded yet.
            </p>
          ) : null}
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
      </section>

      <section className="zen-split">
        <h2 className="zen-split-title">System and Operations</h2>

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
          <h2 className="zen-section-title">Personalization Engine</h2>
          <p className="zen-note" style={{ marginBottom: 10 }}>
            These are the top-performing style buckets learned from your feedback ratings.
          </p>
          {bandit.length === 0 ? (
            <p className="zen-note">No personalization data yet. Add ratings to train preferences.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {bandit.map((arm) => (
                <li key={arm.arm_key} style={{ marginBottom: 6 }}>
                  <strong>{arm.arm_key}</strong> - preference score{" "}
                  {Number(arm.expected_value ?? 0).toFixed(3)} ({arm.pulls ?? 0} ratings)
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}

