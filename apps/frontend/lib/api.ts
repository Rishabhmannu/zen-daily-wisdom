export type SentHistoryItem = {
  id: string;
  sent_date: string;
  sent_at: string;
  arm_tradition?: string;
  arm_tone?: string;
  theme_of_day?: string;
  style_key?: string | null;
  llm_output?: string;
  feedback?: Array<{ id: string; rating?: number; channel?: string; created_at?: string }>;
};

export type BanditItem = {
  arm_key: string;
  alpha: number;
  beta: number;
  pulls: number;
  expected_value: number;
};

export type CheckinItem = {
  id: string;
  checkin_date: string;
  window: "morning" | "midday" | "evening";
  channel: "email" | "telegram" | "dashboard";
  mood_score: number;
  challenge_score?: number | null;
  note?: string | null;
  submitted_at: string;
};

export type DailySeriesPoint = {
  date: string;
  mood: number | null;
  submissions: number;
  windows: string[];
};

export type CheckinStats = {
  completion_rate: number;
  avg_mood_0_100?: number | null;
  avg_mood_legacy_1to5?: number | null;
  avg_challenge?: number | null;
  days_considered: number;
  daily_series?: DailySeriesPoint[];
};

function backendUrl() {
  return process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://localhost:8000";
}

async function fetchJson<T>(path: string, token?: string): Promise<T> {
  const response = await fetch(`${backendUrl()}${path}`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return (await response.json()) as T;
}

export async function fetchHealth() {
  return fetchJson<{ status: string; checks: Record<string, boolean> }>("/health");
}

export async function fetchToday(token: string) {
  return fetchJson<{ data: SentHistoryItem | null }>("/dashboard/today", token);
}

export async function fetchHistory(token: string, limit = 10) {
  return fetchJson<{ data: SentHistoryItem[] }>(`/dashboard/history?limit=${limit}`, token);
}

export async function fetchBandit(token: string, limit = 10) {
  return fetchJson<{ data: BanditItem[] }>(`/dashboard/bandit?limit=${limit}`, token);
}

export async function fetchCheckins(token: string, limit = 30, days = 14) {
  return fetchJson<{ data: CheckinItem[]; stats: CheckinStats }>(
    `/dashboard/checkins?limit=${limit}&days=${days}`,
    token
  );
}

export type DashboardNarrative = {
  body: string;
  source_method: "gemini" | "fallback" | string;
  generated_at: string;
  age_minutes: number;
  is_fresh: boolean;
};

export async function fetchNarrative(token: string) {
  return fetchJson<{ data: DashboardNarrative }>("/dashboard/narrative", token);
}

