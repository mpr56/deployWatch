// Typed fetch wrapper + TanStack Query hooks.
//
// Every request goes through `request` so error handling and JSON parsing exist
// in exactly one place. Vite proxies /api to the FastAPI server (vite.config.ts),
// so these are same-origin in dev.

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import type {
  MonthlyReport,
  PublicStatus,
  StatusPageConfig,
  AlertConfig,
  AlertChannel,
  Check,
  CheckStats,
  SeriesPoint,
  Incident,
  Monitor,
  MonitorSummary,
  TestCheckResult,
  TimeRange,
} from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    // FastAPI puts the useful message in `detail`.
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? res.statusText, res.status);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

// --- queries ---------------------------------------------------------------

/** Dashboard poll. 30s matches the fastest interval bucket worth watching live. */
export function useMonitors() {
  return useQuery({
    queryKey: ["monitors"],
    queryFn: () => request<MonitorSummary[]>("/monitors"),
    refetchInterval: 30_000,
  });
}

export function useMonitor(id: number) {
  return useQuery({
    queryKey: ["monitor", id],
    queryFn: () => request<Monitor>(`/monitors/${id}`),
    enabled: id > 0,
  });
}

export function useChecks(monitorId: number, range: TimeRange = "24h") {
  return useQuery({
    queryKey: ["checks", monitorId, range],
    queryFn: () =>
      request<Check[]>(`/checks?monitor_id=${monitorId}&range=${range}`),
    refetchInterval: 30_000,
  });
}

export function useCheckStats(monitorId: number, range: TimeRange = "24h") {
  return useQuery({
    queryKey: ["check-stats", monitorId, range],
    queryFn: () =>
      request<CheckStats>(`/checks/stats?monitor_id=${monitorId}&range=${range}`),
    refetchInterval: 30_000,
  });
}

export function useCheckSeries(monitorId: number, range: TimeRange = "24h") {
  return useQuery({
    queryKey: ["check-series", monitorId, range],
    queryFn: () =>
      request<SeriesPoint[]>(
        `/checks/series?monitor_id=${monitorId}&range=${range}`,
      ),
    refetchInterval: 30_000,
  });
}

export function useIncidents(monitorId?: number) {
  return useQuery({
    queryKey: ["incidents", monitorId ?? "all"],
    refetchInterval: 30_000,
    queryFn: () =>
      request<Incident[]>(
        monitorId ? `/incidents?monitor_id=${monitorId}` : "/incidents",
      ),
  });
}

// --- mutations -------------------------------------------------------------

export function useCreateMonitor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Monitor>) =>
      request<Monitor>("/monitors", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["monitors"] }),
  });
}

export function useUpdateMonitor(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Monitor>) =>
      request<Monitor>(`/monitors/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["monitors"] });
      qc.invalidateQueries({ queryKey: ["monitor", id] });
    },
  });
}

export function useDeleteMonitor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      request<void>(`/monitors/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["monitors"] }),
  });
}

/** The "Test now" button. Runs one check server-side, saves nothing. */
export function useTestMonitor() {
  return useMutation({
    mutationFn: (body: Partial<Monitor>) =>
      request<TestCheckResult>("/monitors/test", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

// --- incidents & alerts ----------------------------------------------------

export function useIncident(id: number) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () => request<Incident>(`/incidents/${id}`),
    refetchInterval: 30_000,
  });
}

export function useIncidentChecks(id: number) {
  return useQuery({
    queryKey: ["incident-checks", id],
    queryFn: () => request<Check[]>(`/incidents/${id}/checks`),
    refetchInterval: 30_000,
  });
}

export function useAlerts(monitorId: number) {
  return useQuery({
    queryKey: ["alerts", monitorId],
    queryFn: () => request<AlertConfig[]>(`/monitors/${monitorId}/alerts`),
  });
}

export function useCreateAlert(monitorId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { channel: AlertChannel; destination: string }) =>
      request<AlertConfig>(`/monitors/${monitorId}/alerts`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts", monitorId] }),
  });
}

export function useDeleteAlert(monitorId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => request<void>(`/alerts/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts", monitorId] }),
  });
}

export function useTestAlert() {
  return useMutation({
    mutationFn: (id: number) =>
      request<{ ok: boolean }>(`/alerts/${id}/test`, { method: "POST" }),
  });
}

// --- v3: status pages & reports --------------------------------------------

export function usePublicStatus(slug: string) {
  return useQuery({
    queryKey: ["public-status", slug],
    queryFn: () => request<PublicStatus>(`/status/${slug}`),
    refetchInterval: 60_000,
    retry: false,
  });
}

export function useStatusPages() {
  return useQuery({
    queryKey: ["status-pages"],
    queryFn: () => request<StatusPageConfig[]>("/status-pages"),
  });
}

type StatusPageBody = Omit<StatusPageConfig, "id">;

export function useSaveStatusPage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: StatusPageBody & { id?: number }) =>
      request<StatusPageConfig>(id ? `/status-pages/${id}` : "/status-pages", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["status-pages"] }),
  });
}

export function useDeleteStatusPage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      request<void>(`/status-pages/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["status-pages"] }),
  });
}

export function useMonthlyReport(month: string, sla: number) {
  return useQuery({
    queryKey: ["report", month, sla],
    queryFn: () => request<MonthlyReport>(`/reports/monthly?month=${month}&sla=${sla}`),
  });
}
