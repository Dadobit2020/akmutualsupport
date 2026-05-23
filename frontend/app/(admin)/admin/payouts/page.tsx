"use client";

import { useEffect, useState } from "react";
import { adminGetPayouts, adminRecordPayout, Payout, ApiError } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";

export default function PayoutsPage() {
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    amount_dollars: "",
    payout_date: new Date().toISOString().split("T")[0],
    description: "",
    reference: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = () => {
    setLoading(true);
    adminGetPayouts()
      .then(setPayouts)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const amount_cents = Math.round(parseFloat(form.amount_dollars) * 100);
    if (!amount_cents || amount_cents <= 0) { setError("Enter a valid amount."); return; }
    if (!form.description.trim()) { setError("Description is required."); return; }
    if (!confirm(`Record a $${form.amount_dollars} payout on ${form.payout_date}?\n\nThis will debit the PAYOUT_EXP ledger account and credit CASH. This cannot be automatically reversed.`)) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await adminRecordPayout({
        amount_cents,
        payout_date: form.payout_date,
        description: form.description,
        reference: form.reference,
        notes: form.notes,
      });
      setSuccess(`Payout of $${form.amount_dollars} recorded successfully.`);
      setShowForm(false);
      setForm({ amount_dollars: "", payout_date: new Date().toISOString().split("T")[0], description: "", reference: "", notes: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to record payout.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Payouts</h1>
          <p className="text-sm text-gray-500 mt-0.5">Outgoing disbursements — bereavement, emergency, and other payouts</p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setError(""); setSuccess(""); }}
          className="flex items-center gap-2 bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-xl hover:bg-green-800"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Record Payout
        </button>
      </div>

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-800">{success}</div>
      )}

      {showForm && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Record Outgoing Payout</h2>
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-800 mb-4">
            This records cash leaving the association (DR Payout Expense / CR Cash). Use this for bereavement payouts, emergency disbursements, and reimbursements. This entry cannot be automatically reversed — contact your treasurer for adjustments.
          </div>
          {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
          <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Amount ($) *</label>
              <input
                type="number" min="0" step="0.01" placeholder="15000.00"
                value={form.amount_dollars}
                onChange={(e) => setForm({ ...form, amount_dollars: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Payout Date *</label>
              <input
                type="date"
                value={form.payout_date}
                onChange={(e) => setForm({ ...form, payout_date: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Description *</label>
              <input
                type="text" placeholder="e.g. Bereavement payout — Doe family"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Check / Reference #</label>
              <input
                type="text" placeholder="e.g. Check #1004"
                value={form.reference}
                onChange={(e) => setForm({ ...form, reference: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Notes</label>
              <input
                type="text" placeholder="Additional details"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>
            <div className="col-span-2 flex justify-end gap-3">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50">
                Cancel
              </button>
              <button type="submit" disabled={saving}
                className="px-4 py-2 text-sm bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:opacity-50">
                {saving ? "Recording…" : "Record Payout"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800">Payout History</h2>
        </div>
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="animate-spin rounded-full h-6 w-6 border-2 border-green-700 border-t-transparent" />
          </div>
        ) : payouts.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-10">No payouts recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Description</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Amount</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {payouts.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-500 whitespace-nowrap">{formatDate(p.transaction_date)}</td>
                    <td className="px-4 py-3 text-gray-900 font-medium">{p.description}</td>
                    <td className="px-4 py-3 text-right text-red-700 font-semibold whitespace-nowrap">
                      {formatMoney(p.amount_cents)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{p.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-gray-50 border-t border-gray-200">
                  <td colSpan={2} className="px-5 py-3 text-sm font-semibold text-gray-700">Total</td>
                  <td className="px-4 py-3 text-right text-sm font-bold text-red-700">
                    {formatMoney(payouts.reduce((s, p) => s + p.amount_cents, 0))}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
