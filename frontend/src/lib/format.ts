import { ApiError } from "@/lib/api";
import type { StageCode } from "@/lib/types";

export function formatDateTime(iso: string | null | undefined, tz: string): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: tz,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDate(iso: string | null | undefined, tz: string): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: tz, day: "2-digit", month: "2-digit", year: "numeric" }).format(
    new Date(iso),
  );
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.round(diff / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `há ${h} h`;
  const d = Math.round(h / 24);
  if (d < 30) return `há ${d} ${d === 1 ? "dia" : "dias"}`;
  const m = Math.round(d / 30);
  return `há ${m} ${m === 1 ? "mês" : "meses"}`;
}

export function formatMoney(cents: number, currency: string): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(cents / 100);
}

export function errorMessage(err: unknown, fallback = "Não foi possível concluir a operação."): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: unknown } | null;
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { msg?: string; loc?: unknown[] }) => (d.msg ?? "").replace(/^Value error, /, ""))
        .filter(Boolean)
        .join(" · ");
    }
    if (err.status === 0 || err.status >= 500) return "Servidor indisponível. Tente novamente.";
  }
  if (err instanceof TypeError) return "Sem conexão com o servidor.";
  return fallback;
}

export const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  telefone: "Telefone",
  indicacao: "Indicação",
  site: "Site",
  presencial: "Presencial",
  outro: "Outro",
};

export const CONSENT_LABELS: Record<string, string> = {
  opt_in: "Consentiu (opt-in)",
  opt_out: "Recusou (opt-out)",
  nao_informado: "Não informado",
};

export const TEMPERATURE_LABELS: Record<string, string> = {
  none: "Não avaliada",
  frio: "Frio",
  morno: "Morno",
  quente: "Quente",
};

export const LINEAR: StageCode[] = [
  "iniciou_conversa",
  "conversando",
  "consulta_agendada",
  "consulta_realizada",
  "paciente_recorrente",
];
export const REQUIRES_APPOINTMENT: StageCode[] = ["consulta_agendada", "consulta_realizada", "paciente_recorrente"];

// Mirrors backend lib/funnel.is_backward — for UI hints only; the backend enforces.
export function isBackward(from: StageCode, to: StageCode): boolean {
  if (from === "perdido") return true;
  if (to === "perdido") return false;
  return LINEAR.indexOf(to) < LINEAR.indexOf(from);
}

export function needsDialog(from: StageCode, to: StageCode): boolean {
  return to === "perdido" || REQUIRES_APPOINTMENT.includes(to) || isBackward(from, to);
}
