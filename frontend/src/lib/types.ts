// Hand-written mirrors of the backend Pydantic models (backend/models/*.py). Keep in sync.

export type StageCode =
  | "iniciou_conversa"
  | "conversando"
  | "consulta_agendada"
  | "consulta_realizada"
  | "paciente_recorrente"
  | "perdido";

export interface StageConfig {
  code: StageCode;
  label: string;
  color: string;
}

export interface Clinic {
  id: string;
  name: string;
  currency: string;
  timezone: string;
  is_demo: boolean;
  show_lost: boolean;
  stages: StageConfig[];
  created_at: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  role_label: string;
  granted_permissions: string[];
}

export interface Me {
  user: User;
  clinic: Clinic;
  permissions: string[];
}

export interface DemoAccount {
  email: string;
  role: string;
  role_label: string;
}

export interface DemoInfo {
  enabled: boolean;
  accounts: DemoAccount[];
  password: string | null;
}

export interface Member {
  id: string;
  name: string;
  role: string;
  role_label: string;
}

export interface Ok {
  ok: boolean;
  message: string | null;
}

export type ServiceStatus = "ativo" | "inativo";

export interface Service {
  id: string;
  name: string;
  description: string;
  category: string;
  duration_min: number;
  price_cents: number;
  status: ServiceStatus;
  operational_notes: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServiceList {
  items: Service[];
  total: number;
}

export interface Note {
  id: string;
  text: string;
  author_id: string | null;
  author_name: string;
  created_at: string;
}

export interface Contact {
  id: string;
  name: string;
  phone: string;
  email: string;
  channel: string;
  service_interest_id: string | null;
  service_interest_name: string | null;
  owner_id: string | null;
  owner_name: string | null;
  stage: StageCode;
  tags: string[];
  notes: Note[];
  consent: string;
  temperature: string | null;
  next_action: string | null;
  next_action_date: string | null;
  loss_reason: string | null;
  is_demo: boolean;
  entered_at: string;
  last_interaction_at: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ContactList {
  items: Contact[];
  total: number;
  page: number;
  page_size: number;
}

export interface BoardColumn {
  code: StageCode;
  label: string;
  color: string;
  count: number;
  items: Contact[];
}

export interface Board {
  columns: BoardColumn[];
  total: number;
}

export interface ContactEvent {
  id: string;
  contact_id: string;
  type: "created" | "stage_change" | "updated" | "interaction";
  from_stage: string | null;
  to_stage: string | null;
  origin: string;
  user_id: string | null;
  user_name: string | null;
  at: string;
  loss_reason: string | null;
  exception_confirmed: boolean;
  exception_reason: string | null;
  reason: string | null;
  is_backward: boolean;
  summary: string | null;
}

export interface IndicatorDefinition {
  id: string;
  code: string;
  name: string;
  description: string;
  objective: string;
  kind: string;
  formula: string;
  numerator: string | null;
  denominator: string | null;
  unit: string;
  source: string;
  filters: string[];
  inclusion: string;
  exclusion: string;
  frequency: string;
  attribution: string;
  limitations: string;
  available: boolean;
  depends_on: string | null;
  module: string;
}

export interface BreakdownItem {
  key: string;
  label: string;
  value: number;
  color: string | null;
}

export interface IndicatorValue {
  id: string;
  status: "ok" | "sem_dados" | "indisponivel";
  value: number | null;
  previous_value: number | null;
  numerator: number | null;
  denominator: number | null;
  unit: string;
  breakdown: BreakdownItem[];
  notes: string[];
}

export interface IndicatorValues {
  period: string;
  period_label: string;
  period_start: string | null;
  period_end: string | null;
  previous_start: string | null;
  previous_end: string | null;
  target_stage: string;
  window_days: number;
  is_demo: boolean;
  computed_at: string;
  timezone: string;
  values: IndicatorValue[];
}
