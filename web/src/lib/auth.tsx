// Who is using the app, and the gate in front of every change.
//
// The API is the real enforcement (see api/app/auth.py) -- this only decides
// what to show. Visitors browse read-only; pressing anything that changes data
// opens the gate: log in as admin, or start a 5-minute sandbox.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Session } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { request } from "./api";
import { supabase } from "./supabase";

export type Role = "visitor" | "owner" | "sandbox" | "other";

export interface Me {
  auth_enabled: boolean;
  role: Role;
  can_edit: boolean;
  sandbox_expires_at: string | null;
  sandbox_limits: { monitors: number; webhooks: number; status_pages: number };
}

interface AuthState {
  me: Me | undefined;
  canEdit: boolean;
  role: Role;
  /** Open the "admin or sandbox" dialog. */
  openGate: () => void;
  closeGate: () => void;
  gateOpen: boolean;
  /** Run `fn` if the user may edit, otherwise open the gate. */
  guard: (fn: () => void) => void;
  startSandbox: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signInWithGitHub: () => Promise<void>;
  signOut: (reason?: string) => Promise<void>;
  notice: string | null;
  clearNotice: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(!supabase);
  const [gateOpen, setGateOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      // Who you are changes what every query returns.
      qc.invalidateQueries();
    });
    return () => data.subscription.unsubscribe();
  }, [qc]);

  const me = useQuery({
    queryKey: ["me", session?.user.id ?? "anon"],
    queryFn: () => request<Me>("/me"),
    enabled: ready,
    staleTime: 60_000,
  });

  const signOut = useCallback(
    async (reason?: string) => {
      await supabase?.auth.signOut();
      setSession(null);
      if (reason) setNotice(reason);
      qc.invalidateQueries();
    },
    [qc],
  );

  // An admin login with someone else's account: refuse and sign straight out.
  useEffect(() => {
    if (me.data?.role === "other") {
      signOut("That account isn't the admin. Try the sandbox instead.");
    }
  }, [me.data?.role, signOut]);

  const startSandbox = async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.signInAnonymously();
    if (error) throw error;
    await request("/sandbox/start", { method: "POST" });
    await qc.invalidateQueries();
    setGateOpen(false);
  };

  const signInWithPassword = async (email: string, password: string) => {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    setGateOpen(false);
  };

  const signInWithGitHub = async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo: window.location.href },
    });
    if (error) throw error;
  };

  const canEdit = me.data?.can_edit ?? false;

  const value: AuthState = {
    me: me.data,
    canEdit,
    role: me.data?.role ?? "visitor",
    gateOpen,
    openGate: () => setGateOpen(true),
    closeGate: () => setGateOpen(false),
    guard: (fn) => (canEdit ? fn() : setGateOpen(true)),
    startSandbox,
    signInWithPassword,
    signInWithGitHub,
    signOut,
    notice,
    clearNotice: () => setNotice(null),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

/** Seconds left in the sandbox, ticking; null when not in one. */
export function useSandboxCountdown(): number | null {
  const { me } = useAuth();
  const expires = me?.sandbox_expires_at ? new Date(me.sandbox_expires_at).getTime() : null;
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!expires) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [expires]);

  if (!expires) return null;
  return Math.max(0, Math.round((expires - now) / 1000));
}
