// Shapes of the data the API sends. They mirror backend/app/schemas.py.
// TypeScript checks every use of these at build time, so a typo such as
// `incident.titel` is caught before the app ever runs.

export type Severity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "acknowledged" | "investigating" | "resolved" | "closed";
export type Resolution = "true_positive" | "false_positive" | "benign" | "duplicate";
export type Role = "analyst" | "admin";

export interface User {
  id: string;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface EventRecord {
  id: string;
  event_type: string;
  occurred_at: string;
  ingested_at: string;
  source: string;
  actor_id: string;
  resource: string | null;
  outcome: "success" | "failure" | "denied";
  details: Record<string, unknown>;
}

export interface Detection {
  id: string;
  rule_code: string;
  severity: Severity;
  actor_id: string;
  window_start: string;
  window_end: string;
  event_count: number;
  explanation: string;
  source_type: "rule" | "ml";
  model_version: string | null;
  anomaly_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface DetectionDetail extends Detection {
  events: EventRecord[];
}

export interface Rule {
  code: string;
  name: string;
  description: string;
  severity: Severity;
  window_seconds: number;
  threshold: number;
  source_type: "rule" | "ml";
  model_version: string | null;
}

export interface Incident {
  id: string;
  title: string;
  actor_id: string;
  severity: Severity;
  status: IncidentStatus;
  assigned_to: string | null;
  correlation_reason: string;
  first_seen: string;
  last_seen: string;
  resolution: Resolution | null;
  resolution_note: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Note {
  id: string;
  author: string;
  body: string;
  created_at: string;
}

export interface IncidentDetail extends Incident {
  detections: Detection[];
  timeline: EventRecord[];
  notes: Note[];
}

export interface AuditEntry {
  id: string;
  occurred_at: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
}

export interface Stats {
  incidents_by_status: Partial<Record<IncidentStatus, number>>;
  active_incidents_by_severity: Partial<Record<Severity, number>>;
  detections_last_24h_by_rule: Record<string, number>;
  events_last_24h: number;
  unassigned_active_incidents: number;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
  last_used_at: string | null;
}

export interface NewEvent {
  event_type: string;
  occurred_at: string;
  source: string;
  actor_id: string;
  outcome: "success" | "failure" | "denied";
  resource?: string;
  details?: Record<string, unknown>;
}
