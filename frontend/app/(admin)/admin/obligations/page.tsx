"use client";

import { useEffect, useState, useCallback } from "react";
import {
  adminObligations,
  adminSendReminders,
  adminUpdateObligation,
  adminDeleteObligation,
  AdminObligation,
  ApiError,
} from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "open", label: "Open" },
  { value: "partially_paid", label: "Partially Paid" },
  { value: "paid", label: "Paid" },
  { value: "waived", label: "Waived" },
  { value: "written_off", label: "Written Off" },
  { value: "cancelled", label: "Cancelled" },
];

const OBL_STATUS_COLORS: Record<string, string> = {
  open: "bg-amber-100 text-amber-800",
  partially_paid: "bg-blue-100 text-blue-800",
  paid: "bg-green-100 text-green-800",
  waived: "bg-gray-100 text-gray-600",
  written_off: "bg-gray-100 text-gray-500",
  cancelled: "bg-gray-100 text-gray-500",
};

type EditForm = {
  amount_dollars: string;
  due_date: string;
  status: string;
  notes: string;
};

function EditModal({
  obligation,
  onClose,
  onSaved,
}: {
  obligation: AdminObligation;
  onClose: () => void;
  onSaved: (updated: AdminObligation) => void;
}) {
  const [form, setForm] = useState<EditForm>({
    amount_dollars: (obligation.amount_cents / 100).toFixed(2),
    due_date: obligation.due_date,
    status: obligation.status,
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const amount_cents = Math.round(parseFloat(form.amount_dollars) * 100);
    if (!amount_cents || amount_cents <= 0) { setError("Enter a valid amount."); return; }
    setSaving(true);
    setError("");
    try {
      const updated = await adminUpdateObligation(obligation.id, {
        amount_cents,
        due_date: form.due_date,
        status: form.status,
        ...(form.notes.trim() ? { notes: form.notes } : {}),
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-1">Edit Obligation</h2>
        <p className="text-xs text-gray-500 mb-4">{obligation.member_name}</p>
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Amount ($)</label>
              <input
                type="number" min="0" step="0.01"
                value={form.amount_dollars}
                onChange={(e) => setForm({ ...form, amount_dollars: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Due Date</label>
              <input
                type="date"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              <option value="open">Open</option>
              <option value="waived">Waived</option>
              <option value="cancelled">Cancelled</option>
              <option value="written_off">Written Off</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Notes (optional)</label>
            <input
              type="text" placeholder="Reason for change"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 text-sm bg-green-700 text-white font-semibold rounded-lg hover:bg-green-800 disabled:opacity-50">
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ObligationsPage() {
  const [obligations, setObligations] = useState<AdminObligation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState("open");
  const [sortField, setSortField] = useState("due_date");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [remindersSending, setRemindersSending] = useState(false);
  const [reminderResult, setReminderResult] = useState("");
  const [editing, setEditing] = useState<AdminObligation | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = {
        page: String(page),
        sort: sortField,
      };
      if (statusFilter) params.status = statusFilter;
      const res = await adminObligations(params);
      setObligations(res.results);
      setTotal(res.count);
      setTotalPages(res.total_pages);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load obligations.");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, sortField]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [statusFilter, sortField]);

  const handleSendReminders = async () => {
    setRemindersSending(true);
    setReminderResult("");
    try {
      const res = await adminSendReminders();
      setReminderResult(res.detail);
    } catch (err) {
      if (err instanceof ApiError) setReminderResult(`Error: ${err.message}`);
      else setReminderResult("Failed to send reminders.");
    } finally {
      setRemindersSending(false);
    }
  };

  const handleDelete = async (ob: AdminObligation) => {
    if (ob.paid_cents > 0) {
      alert("Cannot delete — payments have been applied. Use Edit to cancel it instead.");
      return;
    }
    if (!confirm(`Delete the obligation for ${ob.member_name} (${formatMoney(ob.amount_cents)}, due ${ob.due_date})?\n\nThis cannot be undone.`)) return;
    setDeletingId(ob.id);
    try {
      await adminDeleteObligation(ob.id);
      setObligations((prev) => prev.filter((o) => o.id !== ob.id));
      setTotal((t) => t - 1);
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to delete.");
    } finally {
      setDeletingId(null);
    }
  };

  const totalOutstanding = obligations.reduce((sum, o) => sum + o.outstanding_cents, 0);

  return (
    <div className="space-y-5 max-w-6xl">
      {editing && (
        <EditModal
          obligation={editing}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            setObligations((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
            setEditing(null);
          }}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Obligations</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} obligations</p>
        </div>
        <Button
          variant="secondary"
          loading={remindersSending}
          onClick={handleSendReminders}
        >
          Send Reminders
        </Button>
      </div>

      {reminderResult && (
        <div className={`rounded-xl px-4 py-3 text-sm ${
          reminderResult.startsWith("Error")
            ? "bg-red-50 border border-red-200 text-red-700"
            : "bg-green-50 border border-green-200 text-green-800"
        }`}>
          {reminderResult}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Status</label>
          <select
            className="px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Sort</label>
          <select
            className="px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            value={sortField}
            onChange={(e) => setSortField(e.target.value)}
          >
            <option value="due_date">Due Date (asc)</option>
            <option value="-due_date">Due Date (desc)</option>
            <option value="amount_cents">Amount (asc)</option>
            <option value="-amount_cents">Amount (desc)</option>
          </select>
        </div>
        {(statusFilter === "open" || statusFilter === "partially_paid") && (
          <div className="ml-auto text-right">
            <p className="text-xs text-gray-400">Total Outstanding</p>
            <p className="text-lg font-bold text-amber-700">{formatMoney(totalOutstanding)}</p>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
          </div>
        ) : obligations.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-12">No obligations found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Member</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Paid</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Outstanding</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Due Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {obligations.map((o) => {
                  const isOverdue =
                    (o.status === "open" || o.status === "partially_paid") &&
                    new Date(o.due_date) < new Date();
                  return (
                    <tr key={o.id} className="hover:bg-gray-50">
                      <td className="px-5 py-3 font-medium text-gray-900">
                        {o.member_name}
                        {o.penalty_weeks_applied > 0 && (
                          <span className="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                            +{o.penalty_weeks_applied}wk penalty
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 capitalize">{o.obligation_type}</td>
                      <td className="px-4 py-3 text-right text-gray-700">{formatMoney(o.amount_cents)}</td>
                      <td className="px-4 py-3 text-right text-green-700">{formatMoney(o.paid_cents)}</td>
                      <td className="px-4 py-3 text-right">
                        <span className={o.outstanding_cents > 0 ? "text-amber-700 font-semibold" : "text-green-700"}>
                          {formatMoney(o.outstanding_cents)}
                        </span>
                      </td>
                      <td className={`px-4 py-3 ${isOverdue ? "text-red-600 font-medium" : "text-gray-500"}`}>
                        {formatDate(o.due_date)}
                        {isOverdue && <span className="ml-1 text-xs">(overdue)</span>}
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          label={o.status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                          colorClass={OBL_STATUS_COLORS[o.status] ?? "bg-gray-100 text-gray-600"}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            onClick={() => setEditing(o)}
                            className="text-xs text-green-700 hover:underline font-medium"
                          >
                            Edit
                          </button>
                          {o.paid_cents === 0 && (
                            <button
                              onClick={() => handleDelete(o)}
                              disabled={deletingId === o.id}
                              className="text-xs text-red-500 hover:underline font-medium disabled:opacity-40"
                            >
                              {deletingId === o.id ? "…" : "Delete"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Page {page} of {totalPages} ({total} obligations)</p>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
