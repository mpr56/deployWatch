// Mirrors api/app/schemas.py. Hand-maintained for now -- if it drifts often,
// generate from http://localhost:8000/openapi.json instead.

export type CheckStatus = "up" | "degraded" | "down";

export interface Monitor {
  id: number;
  name: string;
  url: string;
  interval_secs: number;
  expected_status: number;
  timeout_ms: number;
  degraded_ms: number;
  is_active: boolean;
  created_at: string;
}

export interface MonitorSummary extends Monitor {
  current_status: CheckStatus | null;
  last_response_time_ms: number | null;
  last_checked_at: string | null;
  /** 0-100, or null when the monitor has no checks yet. */
  uptime_24h: number | null;
  /** Oldest to newest. Up to 30 entries. */
  sparkline: CheckStatus[];
}

export interface Check {
  id: number;
  monitor_id: number;
  status: CheckStatus;
  response_time_ms: number | null;
  status_code: number | null;
  error_message: string | null;
  checked_at: string;
}

export interface Incident {
  id: number;
  monitor_id: number;
  started_at: string;
  resolved_at: string | null;
  duration_secs: number | null;
  cause: string | null;
  checks_failed: number;
}

export interface CheckStats {
  count: number;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  uptime_pct: number | null;
}

export interface SeriesPoint {
  bucket: string;
  avg_ms: number | null;
  p95_ms: number | null;
  total: number;
  failed: number;
}

export interface TestCheckResult {
  status: CheckStatus;
  status_code: number | null;
  response_time_ms: number | null;
  error_message: string | null;
}

export type TimeRange = "1h" | "24h" | "7d" | "30d";
