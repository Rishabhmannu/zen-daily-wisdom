import { NextRequest, NextResponse } from "next/server";

function backendUrl() {
  return process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "";
}

export async function POST(request: NextRequest) {
  const auth = request.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ error: "Missing authorization header." }, { status: 401 });
  }

  const backend = backendUrl();
  if (!backend) {
    return NextResponse.json({ error: "NEXT_PUBLIC_BACKEND_URL is not configured." }, { status: 500 });
  }

  const response = await fetch(`${backend}/dashboard/send-now`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body: JSON.stringify({ force: true }),
    cache: "no-store",
  });

  const text = await response.text();
  if (!response.ok) {
    return NextResponse.json({ error: text || "Failed to send." }, { status: response.status });
  }
  return new NextResponse(text, {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
