"use client";

import { useEffect, useState, useCallback } from "react";
import {
  adminPayments,
  adminRecordPayment,
  adminMembers,
  AdminPayment,
  AdminMember,
  ApiError,
} from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const METHOD_OPTIONS = [
  { value: "", label: "All Methods" },
  { value: "cash", label: "Cash" },
  { value: "check", label: "Check" },
  { value: "bank_transfer", label: "Bank Transfer" },
  { value: "online", label: "Online" },
  { value: "other", label: "Other" },
];

const METHOD_LABELS: Record<string, string> = {
  check: "Check",
  bank_transfer: "Bank Transfer",
  cash: "Cash",
  online: "Online",
  other: "Other",
};

function RecordPaymentModal({
  onClose,
  onRecorded,
}: {
  onClose: () => void;
  onRecorded: () => void;
}) {
  const [memberSearch, setMemberSearch] = useState("");
  const [members, setMembers] = useState<AdminMember[]>([]);
  const [selectedMember, setSelectedMember] = useState<AdminMember | null>(null);
  const [searching, setSearching] = useState(false);
  const [form, setForm] = useState({
    amount_dollars: "",
    payment_date: new Date().toISOString().split("T")[0],
    method: "cash",
    reference: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const searchMembers = useCallback(async (q: string) => {
    if (!q.trim()) {
      setMembers([]);
      return;
    }
    setSearching(true);
    try {
      const res = await adminMembers({ search: q, page: "1" });
      setMembers(res.results.slice(0, 8));
    } catch {
      // ignore
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => searchMembers(memberSearch), 300);
    return () => clearTimeout(t);
  }, [memberSearch, searchMembers]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMember) {
      setError("Select a member.");
      return;
    }
    const amount_cents = Math.round(parseFloat(form.amount_dollars) * 100);
    if (isNaN(amount_cents) || amount_cents <= 0) {
      setError("Enter a valid amount.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await adminRecordPayment({
        member_id: selectedMember.id,
        amount_cents,
        payment_date: form.payment_date,
        method: form.method,
        reference: form.reference,
        notes: form.notes,
      });
      onRecorded();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to record payment.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Record Payment</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>
          )}

          {/* Member search */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Member</label>
            {selectedMember ? (
              <div className="flex items-center justify-between px-3 py-2 bg-green-50 border border-green-200 rounded-xl">
                <span className="text-sm font-medium text-green-900">
                  {selectedMember.first_name} {selectedMember.last_name}
                </span>
                <button
                  type="button"
                  onClick={() => { setSelectedMember(null); setMemberSearch(""); }}
                  className="text-xs text-green-600 hover:text-green-800"
                >
                  Change
                </button>
              </div>
            ) : (
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search by name or email..."
                  value={memberSearch}
                  onChange={(e) => setMemberSearch(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                />
                {(members.length > 0 || searching) && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-10 max-h-48 overflow-y-auto">
                    {searching && (
                      <div className="px-3 py-2 text-xs text-gray-400">Searching...</div>
                    )}
                    {members.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => { setSelectedMember(m); setMemberSearch(""); setMembers([]); }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b border-gray-50 last:border-0"
                      >
                        <span className="font-medium text-gray-900">{m.first_name} {m.last_name}</span>
                        {m.email && <span className="text-gray-400 ml-2 text-xs">{m.email}</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Amount (USD)"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="0.00"
              value={form.amount_dollars}
              onChange={(e) => setForm({ ...form, amount_dollars: e.target.value })}
              required
            />
            <Input
              label="Date"
              type="date"
              value={form.payment_date}
              onChange={(e) => setForm({ ...form, payment_date: e.target.value })}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Method</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                value={form.method}
                onChange={(e) => setForm({ ...form, method: e.target.value })}
              >
                <option value="cash">Cash</option>
                <option value="check">Check</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="online">Online</option>
                <option value="other">Other</option>
              </select>
            </div>
            <Input
              label="Reference / Check #"
              value={form.reference}
              onChange={(e) => setForm({ ...form, reference: e.target.value })}
            />
          </div>

          <Input
            label="Notes"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Save Payment
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PaymentsPage() {
  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [method, setMethod] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = { page: String(page) };
      if (method) params.method = method;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await adminPayments(params);
      setPayments(res.results);
      setTotal(res.count);
      setTotalPages(res.total_pages);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load payments.");
    } finally {
      setLoading(false);
    }
  }, [page, method, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [method, dateFrom, dateTo]);

  return (
    <div className="space-y-5 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Payments</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} total payments</p>
        </div>
        <Button onClick={() => setShowModal(true)}>Record Payment</Button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Method</label>
          <select
            className="px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            {METHOD_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <Input
          label="From Date"
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-40"
        />
        <Input
          label="To Date"
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-40"
        />
        {(method || dateFrom || dateTo) && (
          <div className="flex items-end">
            <Button
              variant="ghost"
              onClick={() => { setMethod(""); setDateFrom(""); setDateTo(""); }}
              className="text-xs"
            >
              Clear filters
            </Button>
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
        ) : payments.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-12">No payments found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Member</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Method</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {payments.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-900">{p.member_name}</td>
                    <td className="px-4 py-3 text-right text-green-700 font-semibold">{formatMoney(p.amount_cents)}</td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(p.payment_date)}</td>
                    <td className="px-4 py-3 text-gray-500">{METHOD_LABELS[p.method] ?? p.method}</td>
                    <td className="px-4 py-3 text-gray-400">{p.reference || "—"}</td>
                  </tr>
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
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}

      {showModal && (
        <RecordPaymentModal
          onClose={() => setShowModal(false)}
          onRecorded={() => { setShowModal(false); load(); }}
        />
      )}
    </div>
  );
}
