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
      <button
        onClick={onSendNow}
        disabled={loading}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid #2E4A3C",
          background: loading ? "#d8d8d8" : "#2E4A3C",
          color: "#fff",
          cursor: loading ? "not-allowed" : "pointer"
        }}
      >
        {loading ? "Sending..." : "Send Now"}
      </button>
      {status ? (
        <p style={{ marginTop: 8, marginBottom: 0, fontSize: 13, color: "#3A3A3A" }}>{status}</p>
      ) : null}
    </div>
  );
}

