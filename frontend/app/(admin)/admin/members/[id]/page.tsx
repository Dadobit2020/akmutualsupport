"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  adminMember,
  adminUpdateMember,
  adminRecordPayment,
  AdminMember,
  ApiError,
} from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-600",
  suspended: "bg-red-100 text-red-700",
  deceased: "bg-gray-200 text-gray-500",
  left: "bg-gray-100 text-gray-500",
};

const OBL_STATUS_COLORS: Record<string, string> = {
  open: "bg-amber-100 text-amber-800",
  partially_paid: "bg-blue-100 text-blue-800",
  paid: "bg-green-100 text-green-800",
  waived: "bg-gray-100 text-gray-600",
  written_off: "bg-gray-100 text-gray-500",
  cancelled: "bg-gray-100 text-gray-500",
};

const METHOD_LABELS: Record<string, string> = {
  check: "Check",
  bank_transfer: "Bank Transfer",
  cash: "Cash",
  online: "Online",
  other: "Other",
};

function RecordPaymentForm({
  memberId,
  onRecorded,
  onCancel,
}: {
  memberId: string;
  onRecorded: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    amount_dollars: "",
    payment_date: new Date().toISOString().split("T")[0],
    method: "cash",
    reference: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount_cents = Math.round(parseFloat(form.amount_dollars) * 100);
    if (isNaN(amount_cents) || amount_cents <= 0) {
      setError("Enter a valid amount.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await adminRecordPayment({
        member_id: memberId,
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
    <div className="bg-green-50 border border-green-200 rounded-xl p-4 mt-4">
      <h3 className="text-sm font-semibold text-green-900 mb-3">Record Payment</h3>
      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-3">{error}</p>
      )}
      <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3">
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
        <div className="col-span-2">
          <Input
            label="Notes"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </div>
        <div className="col-span-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Save Payment
          </Button>
        </div>
      </form>
    </div>
  );
}

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [member, setMember] = useState<AdminMember | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<AdminMember>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [showPaymentForm, setShowPaymentForm] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const m = await adminMember(id);
      setMember(m);
      setEditForm({
        first_name: m.first_name,
        last_name: m.last_name,
        email: m.email,
        phone: m.phone,
        status: m.status,
        tier: m.tier,
        notes: m.notes ?? "",
      });
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load member.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const handleSave = async () => {
    if (!member) return;
    setSaving(true);
    setSaveError("");
    try {
      const updated = await adminUpdateMember(member.id, editForm);
      setMember({ ...member, ...updated });
      setEditing(false);
    } catch (err) {
      if (err instanceof ApiError) setSaveError(err.message);
      else setSaveError("Failed to save changes.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
      </div>
    );
  }

  if (error || !member) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-4 text-sm text-red-700">
        {error || "Member not found."}
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Members
      </button>

      {/* Member header card */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              {member.first_name} {member.last_name}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge
                label={member.status.charAt(0).toUpperCase() + member.status.slice(1)}
                colorClass={STATUS_COLORS[member.status] ?? "bg-gray-100 text-gray-600"}
              />
              <span className="text-xs text-gray-400 capitalize">{member.tier}</span>
            </div>
          </div>
          <div className="flex gap-2">
            {!editing && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {!showPaymentForm && (
              <Button onClick={() => setShowPaymentForm(true)}>Record Payment</Button>
            )}
          </div>
        </div>

        {!editing ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Email</p>
              <p className="text-gray-900">{member.email || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Phone</p>
              <p className="text-gray-900">{member.phone || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Join Date</p>
              <p className="text-gray-900">{formatDate(member.join_date)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Total Paid</p>
              <p className="text-green-700 font-semibold">{formatMoney(member.total_paid_cents)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Outstanding</p>
              <p className={member.outstanding_cents > 0 ? "text-amber-700 font-semibold" : "text-green-700"}>
                {formatMoney(member.outstanding_cents)}
              </p>
            </div>
            {member.notes && (
              <div className="col-span-2 sm:col-span-3">
                <p className="text-xs text-gray-400 mb-0.5">Notes</p>
                <p className="text-gray-700">{member.notes}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {saveError && (
              <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{saveError}</p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="First Name"
                value={editForm.first_name ?? ""}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
              />
              <Input
                label="Last Name"
                value={editForm.last_name ?? ""}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
              />
              <Input
                label="Email"
                type="email"
                value={editForm.email ?? ""}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              />
              <Input
                label="Phone"
                value={editForm.phone ?? ""}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
              />
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-700">Status</label>
                <select
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                  value={editForm.status ?? ""}
                  onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="suspended">Suspended</option>
                  <option value="deceased">Deceased</option>
                  <option value="left">Left</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-700">Tier</label>
                <select
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                  value={editForm.tier ?? ""}
                  onChange={(e) => setEditForm({ ...editForm, tier: e.target.value })}
                >
                  <option value="standard">Standard</option>
                  <option value="senior">Senior</option>
                  <option value="family">Family</option>
                </select>
              </div>
              <div className="col-span-2">
                <Input
                  label="Notes"
                  value={editForm.notes ?? ""}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
              <Button loading={saving} onClick={handleSave}>Save Changes</Button>
            </div>
          </div>
        )}

        {showPaymentForm && (
          <RecordPaymentForm
            memberId={member.id}
            onRecorded={() => {
              setShowPaymentForm(false);
              load();
            }}
            onCancel={() => setShowPaymentForm(false)}
          />
        )}
      </div>

      {/* Obligations */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800">Obligations</h2>
        </div>
        {!member.obligations || member.obligations.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">No obligations.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Due Date</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Paid</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Outstanding</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {member.obligations.map((o) => (
                  <tr key={o.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-700 capitalize">{o.obligation_type}</td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(o.due_date)}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{formatMoney(o.amount_cents)}</td>
                    <td className="px-4 py-3 text-right text-green-700">{formatMoney(o.paid_cents)}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={o.outstanding_cents > 0 ? "text-amber-700 font-semibold" : "text-green-700"}>
                        {formatMoney(o.outstanding_cents)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        label={o.status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        colorClass={OBL_STATUS_COLORS[o.status] ?? "bg-gray-100 text-gray-600"}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Payment history */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800">Payment History</h2>
        </div>
        {!member.payments || member.payments.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">No payments recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Method</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {member.payments.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-500">{formatDate(p.payment_date)}</td>
                    <td className="px-4 py-3 text-right text-green-700 font-semibold">{formatMoney(p.amount_cents)}</td>
                    <td className="px-4 py-3 text-gray-500">{METHOD_LABELS[p.method] ?? p.method}</td>
                    <td className="px-4 py-3 text-gray-400">{p.reference || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
