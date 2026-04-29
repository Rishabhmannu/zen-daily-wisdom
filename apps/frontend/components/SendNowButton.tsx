"use client";

import { useState } from "react";

type Props = {
  accessToken: string;
};

export function SendNowButton({ accessToken }: Props) {
  const [status, setStatus] = useState<string>("");
  const [loadingDaily, setLoadingDaily] = useState(false);
  const [loadingCheckin, setLoadingCheckin] = useState(false);

  const onSendNow = async () => {
    setLoadingDaily(true);
    setStatus("");
    try {
      const response = await fetch("/api/actions/send-now", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) {
        const payload = (await response.json()) as { error?: string };
        throw new Error(payload.error || `Send now failed (${response.status})`);
      }
      const payload = (await response.json()) as { status?: string };
      setStatus(`Done: ${payload.status ?? "ok"}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to send");
    } finally {
      setLoadingDaily(false);
    }
  };

  const onSendCheckinNow = async () => {
    setLoadingCheckin(true);
    setStatus("");
    try {
      const response = await fetch("/api/actions/send-checkin-now", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) {
        const payload = (await response.json()) as { error?: string };
        throw new Error(payload.error || `Send check-in failed (${response.status})`);
      }
      const payload = (await response.json()) as { status?: string };
      setStatus(`Check-in reminder: ${payload.status ?? "sent"}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to send check-in");
    } finally {
      setLoadingCheckin(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button onClick={onSendNow} disabled={loadingDaily} className="zen-button">
          {loadingDaily ? "Sending..." : "Send Daily Now"}
        </button>
        <button onClick={onSendCheckinNow} disabled={loadingCheckin} className="zen-button zen-button-secondary">
          {loadingCheckin ? "Sending..." : "Send Check-in Now"}
        </button>
      </div>
      {status ? <p className="zen-note" style={{ marginTop: 8 }}>{status}</p> : null}
    </div>
  );
}

