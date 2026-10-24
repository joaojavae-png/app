export type PeriodPreset = "today" | "7d" | "30d" | "month" | "all" | "custom";

export interface PeriodState {
  preset: PeriodPreset;
  start: string;
  end: string;
}

export const PERIOD_LABELS: Record<PeriodPreset, string> = {
  today: "Hoje",
  "7d": "Últimos 7 dias",
  "30d": "Últimos 30 dias",
  month: "Este mês",
  all: "Todo o período",
  custom: "Intervalo personalizado",
};

export const DEFAULT_PERIOD: PeriodState = { preset: "all", start: "", end: "" };

export function periodParams(p: PeriodState): Record<string, string> {
  if (p.preset === "custom") {
    if (!p.start || !p.end) return { period: "all" };
    return { period: "custom", start: p.start, end: p.end };
  }
  return { period: p.preset };
}

export function toQuery(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
