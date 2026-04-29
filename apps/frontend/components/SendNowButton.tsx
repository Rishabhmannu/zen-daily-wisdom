"use client";

import { useState } from "react";

type Props = {
  accessToken: string;
};

export function SendNowButton({ accessToken }: Props) {
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const onSendNow = async () => {
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://localhost:8000";
    setLoading(true);
    setStatus("");
    try {
      const response = await fetch(`${backend}/dashboard/send-now`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ force: true })
      });
      if (!response.ok) {
        throw new Error(`Send now failed (${response.status})`);
      }
      const payload = (await response.json()) as { status?: string };
      setStatus(`Done: ${payload.status ?? "ok"}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to send");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={onSendNow} disabled={loading} className="zen-button">
        {loading ? "Sending..." : "Send Now"}
      </button>
      {status ? <p className="zen-note" style={{ marginTop: 8 }}>{status}</p> : null}
    </div>
  );
}

