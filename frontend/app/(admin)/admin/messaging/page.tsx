"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  adminMessagingTemplates,
  adminCreateTemplate,
  adminUpdateTemplate,
  adminDeleteTemplate,
  adminMessagingRecipientCount,
  adminSendMessage,
  adminMessagingHistory,
  adminMembers,
  MessageTemplate,
  CommunicationLog,
  AdminMember,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ── Constants ─────────────────────────────────────────────────────────────────

const RECIPIENT_GROUPS = [
  { value: "all_active", label: "All active members" },
  { value: "outstanding_dues", label: "Members with outstanding dues" },
  { value: "suspended", label: "Suspended members" },
  { value: "custom", label: "Custom — pick members" },
];

const TEMPLATE_VARS = [
  "{{member_name}}", "{{first_name}}", "{{last_name}}",
  "{{amount_due}}", "{{due_date}}", "{{event_type}}",
  "{{event_name}}", "{{meeting_date}}",
];

const SAMPLE_VARS: Record<string, string> = {
  member_name: "Yohannes Tesfaye",
  first_name: "Yohannes",
  last_name: "Tesfaye",
  amount_due: "$50.00",
  due_date: "2026-06-30",
  event_type: "bereavement",
  event_name: "June General Meeting",
  meeting_date: "2026-06-15",
  amount: "$50.00",
  date: "2026-05-24",
  method: "Bank Transfer",
  reference: "—",
  portal_url: "portal.addiskidan.org",
  event: "Annual Dues 2026",
  household_name: "Tesfaye household",
};

const STOP_FOOTER = "\n\nReply STOP to unsubscribe.";
const STOP_LEN = STOP_FOOTER.length;

const CATEGORIES = [
  "Dues & Payments", "Events & Meetings", "Benefits & Claims",
  "Bereavement & Support", "Welcome & Onboarding", "General Announcements",
];

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-100 text-gray-600",
  sent: "bg-blue-100 text-blue-700",
  delivered: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-700",
  bounced: "bg-amber-100 text-amber-700",
};

const MOCK_SCHEDULED = [
  { id: "1", name: "Monthly Dues Reminder — June", channel: "both", group: "All active members", scheduled_at: "2026-06-01 08:00", status: "scheduled", count: 45 },
  { id: "2", name: "June General Meeting Reminder", channel: "sms", group: "All active members", scheduled_at: "2026-06-14 09:00", status: "scheduled", count: 38 },
  { id: "3", name: "Overdue Dues Notice", channel: "email", group: "Outstanding dues", scheduled_at: "2026-06-05 10:00", status: "paused", count: 12 },
  { id: "4", name: "Annual Assembly Invitation", channel: "email", group: "All active members", scheduled_at: "2026-07-01 08:00", status: "scheduled", count: 45 },
];

function applyVars(text: string) {
  let out = text;
  for (const [k, v] of Object.entries(SAMPLE_VARS)) {
    out = out.replace(new RegExp(`\\{\\{${k}\\}\\}`, "g"), v);
  }
  return out;
}

function smsSegments(len: number) {
  if (len <= 160) return 1;
  return Math.ceil(len / 153);
}

function channelBadge(ch: string) {
  if (ch === "email") return <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">Email</span>;
  if (ch === "sms") return <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">SMS</span>;
  return (
    <span className="flex gap-1">
      <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">Email</span>
      <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">SMS</span>
    </span>
  );
}

// ── Template Modal ─────────────────────────────────────────────────────────────

function TemplateModal({
  template,
  onClose,
  onSaved,
}: {
  template: MessageTemplate | null;
  onClose: () => void;
  onSaved: (t: MessageTemplate) => void;
}) {
  const [form, setForm] = useState({
    name: template?.name ?? "",
    channel: template?.channel ?? "email",
    subject: template?.subject ?? "",
    body: template?.body ?? "",
    category: template?.category ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  function insertVar(v: string) {
    const el = bodyRef.current;
    if (!el) return;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const newVal = form.body.slice(0, start) + v + form.body.slice(end);
    setForm((f) => ({ ...f, body: newVal }));
    setTimeout(() => { el.focus(); el.setSelectionRange(start + v.length, start + v.length); }, 0);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const saved = template
        ? await adminUpdateTemplate(template.id, form)
        : await adminCreateTemplate(form as any);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save template.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{template ? "Edit Template" : "New Template"}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSave} className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
          {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <Input label="Template Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Category</label>
              <select className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="">— No category —</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            {(["email", "sms"] as const).map((ch) => (
              <button key={ch} type="button"
                onClick={() => setForm({ ...form, channel: ch })}
                className={`px-4 py-2 rounded-xl text-sm font-medium border transition-colors ${
                  form.channel === ch ? "bg-green-700 text-white border-green-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}>
                {ch === "email" ? "Email" : "SMS"}
              </button>
            ))}
          </div>
          {form.channel === "email" && (
            <Input label="Subject" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required />
          )}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Body</label>
            <div className="flex flex-wrap gap-1 mb-1">
              {TEMPLATE_VARS.map((v) => (
                <button key={v} type="button" onClick={() => insertVar(v)}
                  className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 font-mono">
                  {v}
                </button>
              ))}
            </div>
            <textarea
              ref={bodyRef}
              rows={6}
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600 resize-none"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={saving}>Save Template</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Confirm Send Modal ─────────────────────────────────────────────────────────

function ConfirmSendModal({
  count,
  channel,
  groupLabel,
  onConfirm,
  onClose,
  sending,
}: {
  count: number;
  channel: string;
  groupLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  sending: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
            <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <h2 className="text-base font-semibold text-gray-900">Confirm Bulk Send</h2>
        </div>
        <p className="text-sm text-gray-600">
          You are about to send <strong>{channel === "both" ? "email + SMS" : channel}</strong> to{" "}
          <strong>{count} recipients</strong> ({groupLabel}). This cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={sending}>Cancel</Button>
          <Button onClick={onConfirm} loading={sending}>Send Now</Button>
        </div>
      </div>
    </div>
  );
}

// ── Compose Tab ───────────────────────────────────────────────────────────────

function ComposeTab({ templates }: { templates: MessageTemplate[] }) {
  const [channel, setChannel] = useState<"email" | "sms" | "both">("email");
  const [recipientGroup, setRecipientGroup] = useState("all_active");
  const [customMembers, setCustomMembers] = useState<AdminMember[]>([]);
  const [memberSearch, setMemberSearch] = useState("");
  const [memberResults, setMemberResults] = useState<AdminMember[]>([]);
  const [searching, setSearching] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [recipientCount, setRecipientCount] = useState<number | null>(null);
  const [loadingCount, setLoadingCount] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [sending, setSending] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  // Search members for custom picker
  useEffect(() => {
    if (recipientGroup !== "custom") return;
    if (!memberSearch.trim()) { setMemberResults([]); return; }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await adminMembers({ search: memberSearch, page: "1" });
        setMemberResults(res.results.slice(0, 8));
      } catch { /* ignore */ } finally { setSearching(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [memberSearch, recipientGroup]);

  // Load recipient count
  useEffect(() => {
    if (recipientGroup === "custom") {
      setRecipientCount(customMembers.length);
      return;
    }
    setLoadingCount(true);
    adminMessagingRecipientCount(recipientGroup, channel)
      .then((r) => setRecipientCount(r.count))
      .catch(() => setRecipientCount(null))
      .finally(() => setLoadingCount(false));
  }, [recipientGroup, channel, customMembers.length]);

  function insertVar(v: string) {
    const el = bodyRef.current;
    if (!el) return;
    const s = el.selectionStart ?? el.value.length;
    const e2 = el.selectionEnd ?? el.value.length;
    const newVal = body.slice(0, s) + v + body.slice(e2);
    setBody(newVal);
    setTimeout(() => { el.focus(); el.setSelectionRange(s + v.length, s + v.length); }, 0);
  }

  function loadTemplate(id: string) {
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    setTemplateId(id);
    setChannel(t.channel);
    if (t.subject) setSubject(t.subject);
    setBody(t.body);
  }

  const effectiveBody = channel === "sms" ? body + STOP_FOOTER : body;
  const smsBodyLen = effectiveBody.length;
  const usableChars = 160 - STOP_LEN;
  const segments = smsSegments(smsBodyLen);
  const groupLabel = RECIPIENT_GROUPS.find((g) => g.value === recipientGroup)?.label ?? recipientGroup;

  async function handleSend() {
    setSending(true);
    setErrorMsg("");
    try {
      const res = await adminSendMessage({
        channel,
        recipient_group: recipientGroup,
        member_ids: recipientGroup === "custom" ? customMembers.map((m) => m.id) : undefined,
        subject: subject || undefined,
        body,
      });
      setSuccessMsg(res.detail);
      setShowConfirm(false);
      setBody("");
      setSubject("");
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Failed to send.");
      setShowConfirm(false);
    } finally {
      setSending(false);
    }
  }

  const prohibited = ["FREE", "WIN", "CASH", "GUARANTEED", "PRIZE"].filter((w) =>
    body.toUpperCase().includes(w)
  );

  return (
    <div className="space-y-4">
      {successMsg && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-800 flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg("")} className="text-green-600 hover:text-green-800 ml-3">✕</button>
        </div>
      )}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg("")} className="text-red-600 ml-3">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Compose panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
          {/* Channel */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">Channel</label>
            <div className="flex gap-2">
              {(["email", "sms", "both"] as const).map((ch) => (
                <button key={ch} type="button" onClick={() => setChannel(ch)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium border transition-colors ${
                    channel === ch ? "bg-green-700 text-white border-green-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}>
                  {ch === "both" ? "Email + SMS" : ch === "email" ? "Email" : "SMS"}
                </button>
              ))}
            </div>
          </div>

          {/* Recipients */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Recipients</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
              value={recipientGroup}
              onChange={(e) => { setRecipientGroup(e.target.value); setCustomMembers([]); }}
            >
              {RECIPIENT_GROUPS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
            {recipientGroup === "custom" && (
              <div className="mt-2 space-y-2">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search members..."
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                  />
                  {(memberResults.length > 0 || searching) && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-10 max-h-40 overflow-y-auto">
                      {searching && <div className="px-3 py-2 text-xs text-gray-400">Searching...</div>}
                      {memberResults.filter((m) => !customMembers.find((c) => c.id === m.id)).map((m) => (
                        <button key={m.id} type="button"
                          onClick={() => { setCustomMembers((prev) => [...prev, m]); setMemberSearch(""); setMemberResults([]); }}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b border-gray-50 last:border-0">
                          <span className="font-medium">{m.first_name} {m.last_name}</span>
                          {m.email && <span className="text-gray-400 ml-2 text-xs">{m.email}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {customMembers.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {customMembers.map((m) => (
                      <span key={m.id} className="inline-flex items-center gap-1 text-xs bg-green-50 text-green-800 border border-green-200 rounded-full px-2 py-1">
                        {m.first_name} {m.last_name}
                        <button onClick={() => setCustomMembers((prev) => prev.filter((x) => x.id !== m.id))} className="text-green-500 hover:text-green-700">✕</button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Template picker */}
          {templates.length > 0 && (
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Load Template</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                value={templateId}
                onChange={(e) => loadTemplate(e.target.value)}
              >
                <option value="">— select a template —</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          )}

          {/* Subject (email) */}
          {channel !== "sms" && (
            <Input
              label="Subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Message subject..."
            />
          )}

          {/* Variables */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Insert variable</label>
            <div className="flex flex-wrap gap-1">
              {TEMPLATE_VARS.map((v) => (
                <button key={v} type="button" onClick={() => insertVar(v)}
                  className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 font-mono">
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Body */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium text-gray-700">Message</label>
              {channel !== "email" && (
                <span className={`text-xs ${body.length > usableChars ? "text-amber-600" : "text-gray-400"}`}>
                  {body.length}/{usableChars} chars usable · {segments} segment{segments !== 1 ? "s" : ""}
                </span>
              )}
            </div>
            <textarea
              ref={bodyRef}
              rows={7}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write your message..."
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600 resize-none"
            />
            {channel !== "email" && (
              <p className="text-xs text-gray-400 mt-1">
                Opt-out footer (29 chars) appended automatically: <em>"Reply STOP to unsubscribe."</em>
              </p>
            )}
            {prohibited.length > 0 && (
              <p className="text-xs text-amber-600 mt-1">
                Carrier warning: message contains flagged word(s): {prohibited.join(", ")}
              </p>
            )}
          </div>

          {/* Send bar */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-gray-500">
              {loadingCount ? "Counting..." : recipientCount !== null ? `${recipientCount} recipient${recipientCount !== 1 ? "s" : ""}` : ""}
            </span>
            <Button
              disabled={!body.trim() || (channel !== "sms" && !subject.trim()) || (recipientGroup === "custom" && customMembers.length === 0)}
              onClick={() => setShowConfirm(true)}
            >
              Send Message
            </Button>
          </div>
        </div>

        {/* Preview panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Preview — sample member: Yohannes Tesfaye</h3>
          <div className={`rounded-xl p-4 text-sm space-y-2 ${channel !== "email" ? "bg-purple-50 border border-purple-100" : "bg-blue-50 border border-blue-100"}`}>
            {channel !== "sms" && subject && (
              <p className="font-semibold text-gray-800 border-b border-gray-200 pb-2">{applyVars(subject)}</p>
            )}
            <pre className="whitespace-pre-wrap font-sans text-gray-700 text-sm">
              {applyVars(body) || <span className="text-gray-400 italic">Your message will appear here…</span>}
              {channel !== "email" && body && <span className="text-gray-400">{STOP_FOOTER}</span>}
            </pre>
          </div>
          {channel !== "email" && body && (
            <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
              <span>Total sent length: {effectiveBody.length} chars</span>
              <span>{segments} SMS segment{segments !== 1 ? "s" : ""}</span>
            </div>
          )}
          <p className="text-xs text-gray-400 mt-4">
            Sent from: <strong>Addis Kidan Association</strong> · From: noreply@addiskidan.org
          </p>
        </div>
      </div>

      {showConfirm && (
        <ConfirmSendModal
          count={recipientCount ?? 0}
          channel={channel}
          groupLabel={groupLabel}
          onConfirm={handleSend}
          onClose={() => setShowConfirm(false)}
          sending={sending}
        />
      )}
    </div>
  );
}

// ── Templates Tab ─────────────────────────────────────────────────────────────

function TemplatesTab({
  templates,
  onRefresh,
}: {
  templates: MessageTemplate[];
  onRefresh: () => void;
}) {
  const [search, setSearch] = useState("");
  const [editingTemplate, setEditingTemplate] = useState<MessageTemplate | null | "new">(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function handleDelete(t: MessageTemplate) {
    if (!confirm(`Delete template "${t.name}"? This cannot be undone.`)) return;
    setDeletingId(t.id);
    try {
      await adminDeleteTemplate(t.id);
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete.");
    } finally {
      setDeletingId(null);
    }
  }

  function handleDuplicate(t: MessageTemplate) {
    setEditingTemplate({ ...t, id: "", name: `${t.name} (copy)` } as any);
  }

  const filtered = templates.filter((t) =>
    `${t.name} ${t.category}`.toLowerCase().includes(search.toLowerCase())
  );
  const byCategory = CATEGORIES.reduce<Record<string, MessageTemplate[]>>((acc, cat) => {
    const items = filtered.filter((t) => t.category === cat);
    if (items.length > 0) acc[cat] = items;
    return acc;
  }, {});
  const uncategorized = filtered.filter((t) => !t.category || !CATEGORIES.includes(t.category));

  return (
    <div className="space-y-4">
      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="flex gap-3">
        <div className="flex-1">
          <Input placeholder="Search templates..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button onClick={() => setEditingTemplate("new")}>+ New Template</Button>
      </div>

      {filtered.length === 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center">
          <p className="text-gray-400 text-sm">No templates yet — create your first one.</p>
          <Button className="mt-4" onClick={() => setEditingTemplate("new")}>Create Template</Button>
        </div>
      )}

      {Object.entries(byCategory).map(([cat, items]) => (
        <div key={cat}>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{cat}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {items.map((t) => (
              <TemplateCard key={t.id} template={t} deletingId={deletingId}
                onEdit={() => setEditingTemplate(t)}
                onDuplicate={() => handleDuplicate(t)}
                onDelete={() => handleDelete(t)} />
            ))}
          </div>
        </div>
      ))}

      {uncategorized.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Other</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {uncategorized.map((t) => (
              <TemplateCard key={t.id} template={t} deletingId={deletingId}
                onEdit={() => setEditingTemplate(t)}
                onDuplicate={() => handleDuplicate(t)}
                onDelete={() => handleDelete(t)} />
            ))}
          </div>
        </div>
      )}

      {(editingTemplate === "new" || (editingTemplate && editingTemplate !== "new")) && (
        <TemplateModal
          template={editingTemplate === "new" ? null : editingTemplate}
          onClose={() => setEditingTemplate(null)}
          onSaved={() => { setEditingTemplate(null); onRefresh(); }}
        />
      )}
    </div>
  );
}

function TemplateCard({
  template: t,
  deletingId,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  template: MessageTemplate;
  deletingId: string | null;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-gray-900 leading-snug">{t.name}</span>
        {channelBadge(t.channel)}
      </div>
      <p className="text-xs text-gray-500 line-clamp-2">{t.body}</p>
      <div className="flex items-center gap-3 pt-1">
        <button onClick={onEdit} className="text-xs text-green-700 hover:underline">Edit</button>
        <button onClick={onDuplicate} className="text-xs text-gray-500 hover:underline">Duplicate</button>
        <button onClick={onDelete} disabled={deletingId === t.id}
          className="text-xs text-red-500 hover:underline disabled:opacity-40">
          {deletingId === t.id ? "…" : "Delete"}
        </button>
      </div>
    </div>
  );
}

// ── Scheduled Tab (mock) ──────────────────────────────────────────────────────

function ScheduledTab() {
  const statusColors: Record<string, string> = {
    scheduled: "bg-amber-100 text-amber-700",
    paused: "bg-gray-100 text-gray-500",
    failed: "bg-red-100 text-red-700",
  };

  return (
    <div className="space-y-4">
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
        Scheduled messaging is coming soon. Recurring sends (monthly dues reminders, meeting alerts) will be configurable here.
      </div>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Name</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Channel</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Recipients</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Scheduled</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {MOCK_SCHEDULED.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="px-5 py-3 font-medium text-gray-900">{s.name}</td>
                <td className="px-4 py-3">{channelBadge(s.channel)}</td>
                <td className="px-4 py-3 text-gray-500">{s.group} ({s.count})</td>
                <td className="px-4 py-3 text-gray-500">{s.scheduled_at}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColors[s.status] ?? ""}`}>
                    {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── History Tab ───────────────────────────────────────────────────────────────

function HistoryTab() {
  const [history, setHistory] = useState<CommunicationLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [channel, setChannel] = useState("");
  const [msgStatus, setMsgStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = { page: String(page) };
      if (channel) params.channel = channel;
      if (msgStatus) params.status = msgStatus;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await adminMessagingHistory(params);
      setHistory(res.results);
      setTotal(res.count);
      setTotalPages(res.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load history.");
    } finally {
      setLoading(false);
    }
  }, [page, channel, msgStatus, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [channel, msgStatus, dateFrom, dateTo]);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Channel</label>
          <select className="px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="">All</option>
            <option value="email">Email</option>
            <option value="sms">SMS</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Status</label>
          <select className="px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            value={msgStatus} onChange={(e) => setMsgStatus(e.target.value)}>
            <option value="">All</option>
            <option value="queued">Queued</option>
            <option value="sent">Sent</option>
            <option value="delivered">Delivered</option>
            <option value="failed">Failed</option>
            <option value="bounced">Bounced</option>
          </select>
        </div>
        <Input label="From Date" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" />
        <Input label="To Date" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" />
        {(channel || msgStatus || dateFrom || dateTo) && (
          <div className="flex items-end">
            <Button variant="ghost" onClick={() => { setChannel(""); setMsgStatus(""); setDateFrom(""); setDateTo(""); }} className="text-xs">
              Clear
            </Button>
          </div>
        )}
        <div className="ml-auto flex items-end">
          <span className="text-xs text-gray-400 self-center">{total} messages</span>
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-7 w-7 border-2 border-green-700 border-t-transparent" />
          </div>
        ) : history.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-12">No messages sent yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Channel</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Recipient</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Subject / Preview</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {history.map((c) => (
                  <>
                    <tr key={c.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpanded(expanded === c.id ? null : c.id)}>
                      <td className="px-5 py-3 text-gray-500 whitespace-nowrap">
                        {new Date(c.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">{channelBadge(c.channel)}</td>
                      <td className="px-4 py-3 text-gray-700">
                        <span className="font-medium">{c.recipient_name || "—"}</span>
                        <span className="text-gray-400 block text-xs">{c.recipient_address}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 max-w-xs">
                        {c.subject && <span className="font-medium text-gray-700 block truncate">{c.subject}</span>}
                        <span className="text-xs truncate block">{c.body_preview}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-600"}`}>
                          {c.status}
                        </span>
                      </td>
                    </tr>
                    {expanded === c.id && (
                      <tr key={`${c.id}-exp`} className="bg-gray-50">
                        <td colSpan={5} className="px-5 py-3">
                          <pre className="text-xs text-gray-600 whitespace-pre-wrap font-sans">{c.body_preview}</pre>
                          {c.error_message && <p className="text-xs text-red-600 mt-1">Error: {c.error_message}</p>}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Page {page} of {totalPages}</p>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
            <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "compose" | "templates" | "scheduled" | "history";

export default function MessagingPage() {
  const [tab, setTab] = useState<Tab>("compose");
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      setTemplates(await adminMessagingTemplates());
    } catch { /* ignore */ } finally {
      setLoadingTemplates(false);
    }
  }, []);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const TABS: { key: Tab; label: string }[] = [
    { key: "compose", label: "Compose & Send" },
    { key: "templates", label: `Templates (${templates.length})` },
    { key: "scheduled", label: "Scheduled" },
    { key: "history", label: "History" },
  ];

  return (
    <div className="space-y-5 max-w-6xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Messaging</h1>
        <p className="text-sm text-gray-500 mt-0.5">Send emails and SMS to members — individual or bulk</p>
      </div>

      {/* Tab nav */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-1.5 flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors ${
              tab === t.key ? "bg-green-700 text-white" : "text-gray-600 hover:bg-gray-100"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "compose" && (loadingTemplates ? null : <ComposeTab templates={templates} />)}
      {tab === "templates" && <TemplatesTab templates={templates} onRefresh={loadTemplates} />}
      {tab === "scheduled" && <ScheduledTab />}
      {tab === "history" && <HistoryTab />}
    </div>
  );
}
