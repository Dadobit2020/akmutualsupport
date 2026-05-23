"use client";

import { useEffect, useState, useCallback } from "react";
import {
  adminObligations,
  adminSendReminders,
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
];

const OBL_STATUS_COLORS: Record<string, string> = {
  open: "bg-amber-100 text-amber-800",
  partially_paid: "bg-blue-100 text-blue-800",
  paid: "bg-green-100 text-green-800",
  waived: "bg-gray-100 text-gray-600",
  written_off: "bg-gray-100 text-gray-500",
  cancelled: "bg-gray-100 text-gray-500",
};

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

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, sortField]);

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

  const totalOutstanding = obligations.reduce((sum, o) => sum + o.outstanding_cents, 0);

  return (
    <div className="space-y-5 max-w-6xl">
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

      {/* Filters */}
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
        {statusFilter === "open" || statusFilter === "partially_paid" ? (
          <div className="ml-auto text-right">
            <p className="text-xs text-gray-400">Total Outstanding</p>
            <p className="text-lg font-bold text-amber-700">{formatMoney(totalOutstanding)}</p>
          </div>
        ) : null}
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
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {obligations.map((o) => {
                  const isOverdue =
                    (o.status === "open" || o.status === "partially_paid") &&
                    new Date(o.due_date) < new Date();
                  return (
                    <tr key={o.id} className="hover:bg-gray-50">
                      <td className="px-5 py-3 font-medium text-gray-900">{o.member_name}</td>
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
