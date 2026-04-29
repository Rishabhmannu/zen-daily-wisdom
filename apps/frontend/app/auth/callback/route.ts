import { NextResponse } from "next/server";

import { createServerClient } from "@supabase/ssr";
import type { EmailOtpType } from "@supabase/supabase-js";
import { cookies } from "next/headers";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const tokenHash = url.searchParams.get("token_hash");
  const token = url.searchParams.get("token");
  const type = url.searchParams.get("type");
  const nextParam = url.searchParams.get("next") || "/dashboard";
  const next = nextParam.startsWith("/") ? nextParam : "/dashboard";
  const redirectResponse = NextResponse.redirect(new URL(next, request.url));

  const cookieStore = await cookies();
  type CookieToSet = {
    name: string;
    value: string;
    options?: Parameters<typeof redirectResponse.cookies.set>[2];
  };
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          cookiesToSet.forEach(({ name, value, options }) => {
            redirectResponse.cookies.set(name, value, options);
          });
        }
      }
    }
  );

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("next", next);
      loginUrl.searchParams.set("error", error.message || "auth_exchange_failed");
      return NextResponse.redirect(loginUrl);
    }
  } else {
    const otpToken = tokenHash || token;
    if (otpToken && type) {
      const { error } = await supabase.auth.verifyOtp({
        token_hash: otpToken,
        type: type as EmailOtpType
      });
      if (error) {
        const loginUrl = new URL("/login", request.url);
        loginUrl.searchParams.set("next", next);
        loginUrl.searchParams.set("error", error.message || "otp_verification_failed");
        return NextResponse.redirect(loginUrl);
      }
    } else {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("next", next);
      loginUrl.searchParams.set("error", "missing_auth_params");
      return NextResponse.redirect(loginUrl);
    }
  }

  return redirectResponse;
}

