/**
 * Thin API client wrapping the Django REST backend.
 * All money values from the API are in cents (integers).
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Token management ──────────────────────────────────────────────────────────

const TOKEN_KEY = "ak_access";
const REFRESH_KEY = "ak_refresh";

export function saveTokens(access: string, refresh: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  const res = await fetch(`${BASE_URL}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return null;
  }
  const data = await res.json();
  saveTokens(data.access, refresh);
  return data.access;
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const newToken = await refreshAccessToken();
    if (newToken) return apiFetch<T>(path, options, false);
    throw new ApiError(401, "Session expired. Please log in again.");
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.error?.detail ?? body?.detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string | object
  ) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginPayload {
  email: string;
  password: string;
  mfa_token?: string;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  mfa_enabled: boolean;
  is_active: boolean;
  roles?: string[];
}

const ADMIN_ROLES = new Set(["super_admin", "treasurer", "secretary", "chairperson"]);

export function isAdmin(user: User | null): boolean {
  if (!user || !user.roles) return false;
  return user.roles.some((r) => ADMIN_ROLES.has(r));
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/token/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/auth/me/");
}

export async function updateProfile(data: Partial<User>): Promise<User> {
  return apiFetch<User>("/auth/me/", { method: "PATCH", body: JSON.stringify(data) });
}

export async function changePassword(current_password: string, new_password: string) {
  return apiFetch("/auth/change-password/", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
}

// ── Obligations ───────────────────────────────────────────────────────────────

export interface Obligation {
  id: string;
  obligation_type: string;
  event: string | null;
  event_description: string | null;
  amount_cents: number;
  paid_cents: number;
  outstanding_cents: number;
  due_date: string;
  status: string;
  waiver_reason: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export async function getMyObligations(params?: Record<string, string>): Promise<Obligation[]> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<Obligation[]>(`/me/obligations/${qs}`);
}

// ── Payments ──────────────────────────────────────────────────────────────────

export interface Payment {
  id: string;
  amount_cents: number;
  payment_date: string;
  method: string;
  reference: string;
  applications: { obligation: string; applied_cents: number }[];
  created_at: string;
}

export async function getMyPayments(): Promise<Payment[]> {
  return apiFetch<Payment[]>("/me/payments/");
}

// ── Member balance ────────────────────────────────────────────────────────────

export interface MemberBalance {
  outstanding_cents: number;
  ledger_balance_cents: number;
  open_obligation_count: number;
}

export async function getMyBalance(): Promise<MemberBalance> {
  return apiFetch<MemberBalance>("/me/balance/");
}

// ── PDF downloads ────────────────────────────────────────────────────────────

async function apiFetchBlob(path: string): Promise<Blob> {
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { headers });

  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) return apiFetchBlob(path);
    throw new ApiError(401, "Session expired. Please log in again.");
  }
  if (!res.ok) {
    throw new ApiError(res.status, `HTTP ${res.status}`);
  }
  return res.blob();
}

export async function downloadReceipt(paymentId: string): Promise<void> {
  const blob = await apiFetchBlob(`/me/payments/${paymentId}/receipt/`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `receipt-${paymentId.slice(0, 8)}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadStatement(): Promise<void> {
  const blob = await apiFetchBlob("/me/statement/");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "statement.pdf";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface DashboardData {
  outstanding_cents: number;
  active_events: number;
  pending_approval_events: number;
  reconciliation_review_queue: number;
  payments_last_30_days_cents: number;
  active_members: number;
}

export async function getDashboard(): Promise<DashboardData> {
  return apiFetch<DashboardData>("/reports/dashboard/");
}

// ── Members ───────────────────────────────────────────────────────────────────

export interface Member {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  phone_whatsapp: string;
  address: string;
  preferred_language: string;
}

// ── AI Assistant ──────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  response: string;
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[]
): Promise<string> {
  const data = await apiFetch<ChatResponse>("/me/chat/", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
  return data.response;
}

// ── Members ───────────────────────────────────────────────────────────────────

export async function getMemberProfile(id: string): Promise<Member> {
  return apiFetch<Member>(`/members/${id}/`);
}

export async function updateMemberProfile(id: string, data: Partial<Member>): Promise<Member> {
  return apiFetch<Member>(`/members/${id}/`, { method: "PATCH", body: JSON.stringify(data) });
}

// ── Admin API types ───────────────────────────────────────────────────────────

export interface AdminRecentPayment {
  id: string;
  member_id: string | null;
  member_name: string;
  amount_cents: number;
  payment_date: string;
  method: string;
  reference: string;
  notes: string;
}

export interface AdminDashboard {
  total_members: number;
  active_members: number;
  total_collected_cents: number;
  total_payouts_cents: number;
  outstanding_cents: number;
  members_this_month: number;
  recent_payments: AdminRecentPayment[];
  obligations_by_status: Record<string, number>;
}

export interface FamilyMember {
  id: string;
  first_name: string;
  last_name: string;
  first_name_am: string;
  last_name_am: string;
  relationship: string;
  date_of_birth: string;
  gender: string;
  age: number;
  is_active: boolean;
  notes: string;
}

export interface AdminMember {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  join_date: string;
  status: string;
  tier: string;
  total_paid_cents: number;
  outstanding_cents: number;
  notes?: string;
  address?: string;
  phone_whatsapp?: string;
  obligations?: AdminObligation[];
  payments?: AdminPayment[];
  family_members?: FamilyMember[];
}

export async function adminFamilyMembers(memberId: string): Promise<FamilyMember[]> {
  return apiFetch<FamilyMember[]>(`/admin/members/${memberId}/family/`);
}

export async function adminAddFamilyMember(
  memberId: string,
  data: {
    first_name: string;
    last_name: string;
    first_name_am?: string;
    last_name_am?: string;
    relationship: string;
    date_of_birth: string;
    gender?: string;
    notes?: string;
  }
): Promise<FamilyMember> {
  return apiFetch<FamilyMember>(`/admin/members/${memberId}/family/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function adminUpdateFamilyMember(
  memberId: string,
  fmId: string,
  data: Partial<FamilyMember>
): Promise<FamilyMember> {
  return apiFetch<FamilyMember>(`/admin/members/${memberId}/family/${fmId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function adminRemoveFamilyMember(memberId: string, fmId: string): Promise<void> {
  await apiFetch<void>(`/admin/members/${memberId}/family/${fmId}/`, { method: "DELETE" });
}

export interface AdminPayment {
  id: string;
  member_id: string | null;
  member_name: string;
  amount_cents: number;
  payment_date: string;
  method: string;
  reference: string;
  notes: string;
}

export interface AdminObligation {
  id: string;
  obligation_type: string;
  member_id: string;
  member_name: string;
  amount_cents: number;
  paid_cents: number;
  outstanding_cents: number;
  due_date: string;
  status: string;
  event_id: string | null;
}

export interface AdminEvent {
  id: string;
  event_type: string;
  household: string;
  household_id: string;
  event_date: string;
  description: string;
  payout_amount_cents: number;
  status: string;
}

export interface AdminPaginatedResponse<T> {
  count: number;
  page: number;
  total_pages: number;
  results: T[];
}

// ── Admin API functions ───────────────────────────────────────────────────────

export async function adminDashboard(): Promise<AdminDashboard> {
  return apiFetch<AdminDashboard>("/admin/dashboard/");
}

export async function adminMembers(
  params?: Record<string, string>
): Promise<AdminPaginatedResponse<AdminMember>> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<AdminPaginatedResponse<AdminMember>>(`/admin/members/${qs}`);
}

export async function adminMember(id: string): Promise<AdminMember> {
  return apiFetch<AdminMember>(`/admin/members/${id}/`);
}

export async function adminCreateMember(
  data: Partial<AdminMember>
): Promise<AdminMember> {
  return apiFetch<AdminMember>("/admin/members/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function adminUpdateMember(
  id: string,
  data: Partial<AdminMember>
): Promise<AdminMember> {
  return apiFetch<AdminMember>(`/admin/members/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function adminPayments(
  params?: Record<string, string>
): Promise<AdminPaginatedResponse<AdminPayment>> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<AdminPaginatedResponse<AdminPayment>>(`/admin/payments/${qs}`);
}

export interface RecordPaymentPayload {
  member_id: string;
  amount_cents: number;
  payment_date: string;
  method: string;
  reference?: string;
  notes?: string;
}

export async function adminRecordPayment(
  data: RecordPaymentPayload
): Promise<AdminPayment> {
  return apiFetch<AdminPayment>("/admin/payments/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function adminObligations(
  params?: Record<string, string>
): Promise<AdminPaginatedResponse<AdminObligation>> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<AdminPaginatedResponse<AdminObligation>>(`/admin/obligations/${qs}`);
}

export async function adminUpdateObligation(
  id: string,
  data: { amount_cents?: number; due_date?: string; status?: string; notes?: string }
): Promise<AdminObligation> {
  return apiFetch<AdminObligation>(`/admin/obligations/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function adminDeleteObligation(id: string): Promise<void> {
  await apiFetch<void>(`/admin/obligations/${id}/`, { method: "DELETE" });
}

export async function adminSendReminders(): Promise<{ queued: number; detail: string }> {
  return apiFetch<{ queued: number; detail: string }>("/admin/obligations/send-reminders/", {
    method: "POST",
  });
}

export async function adminEvents(
  params?: Record<string, string>
): Promise<AdminPaginatedResponse<AdminEvent>> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<AdminPaginatedResponse<AdminEvent>>(`/admin/events/${qs}`);
}

export interface CreateEventPayload {
  event_type: string;
  household_name: string;
  event_date: string;
  payout_amount_cents: number;
  description?: string;
}

export async function adminCreateEvent(data: CreateEventPayload): Promise<AdminEvent> {
  return apiFetch<AdminEvent>("/admin/events/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Settings ──────────────────────────────────────────────────────────────────

export interface OrgSettings {
  entrance_fee_cents: number;
  maintenance_fee_cents: number;
  maintenance_fee_anchor_month: number;
  assessment_due_days: number;
  active_member_count: number;
  audit_log: {
    field: string;
    old_value: string;
    new_value: string;
    changed_by: string;
    changed_at: string;
  }[];
}

export interface AssessmentPreview {
  total_payout_cents: number;
  active_member_count: number;
  per_member_cents: number;
  due_date: string;
}

export async function adminGetSettings(): Promise<OrgSettings> {
  return apiFetch<OrgSettings>("/admin/settings/");
}

export async function adminUpdateSettings(
  data: Partial<Pick<OrgSettings, "entrance_fee_cents" | "maintenance_fee_cents" | "maintenance_fee_anchor_month" | "assessment_due_days">>
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/admin/settings/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function adminAssessmentPreview(amountDollars: number): Promise<AssessmentPreview> {
  return apiFetch<AssessmentPreview>(`/admin/assessment/preview/?amount=${amountDollars}`);
}

export async function adminProcessAssessment(data: {
  total_cents: number;
  per_member_cents: number;
  due_date: string;
  description: string;
}): Promise<{ ok: boolean; member_count: number; per_member_cents: number; due_date: string }> {
  return apiFetch("/admin/assessment/process/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Annual Dues & Payouts ─────────────────────────────────────────────────────

export async function adminGenerateAnnualDues(data: {
  year: number;
  amount_cents: number;
  due_date: string;
}): Promise<{ ok: boolean; created: number; skipped: number; year: number; amount_cents: number; due_date: string }> {
  return apiFetch("/admin/obligations/generate-annual-dues/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface Payout {
  id: string;
  description: string;
  transaction_date: string;
  amount_cents: number;
  notes: string;
}

export async function adminGetPayouts(): Promise<Payout[]> {
  return apiFetch<Payout[]>("/admin/payouts/");
}

export async function adminRecordPayout(data: {
  amount_cents: number;
  payout_date: string;
  description: string;
  reference?: string;
  notes?: string;
}): Promise<{ ok: boolean; transaction_id: string; amount_cents: number; payout_date: string }> {
  return apiFetch("/admin/payouts/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
