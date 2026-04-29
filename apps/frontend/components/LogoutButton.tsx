"use client";

import { createClient } from "@/lib/supabase/client";

export function LogoutButton() {
  const onLogout = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.assign("/login");
  };

  return (
    <button type="button" className="zen-button zen-button-secondary" onClick={onLogout}>
      Log out
    </button>
  );
}
