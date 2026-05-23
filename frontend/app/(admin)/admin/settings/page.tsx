"use client";

import { useEffect, useState } from "react";
import {
  adminGetSettings,
  adminUpdateSettings,
  adminAssessmentPreview,
  adminProcessAssessment,
  adminGenerateAnnualDues,
  OrgSettings,
  AssessmentPreview,
  ApiError,
} from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";

const MONTH_NAMES = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  // Fee fields (dollars for display, cents for storage)
  const [entranceFee, setEntranceFee] = useState("");
  const [maintenanceFee, setMaintenanceFee] = useState("");
  const [anchorMonth, setAnchorMonth] = useState("1");
  const [dueDays, setDueDays] = useState("30");

  // Annual dues
  const [duesYear, setDuesYear] = useState(String(new Date().getFullYear()));
  const [duesAmount, setDuesAmount] = useState("");
  const [duesDueDate, setDuesDueDate] = useState(`${new Date().getFullYear()}-12-31`);
  const [duesLoading, setDuesLoading] = useState(false);
  const [duesResult, setDuesResult] = useState("");

  // Assessment calculator
  const [payoutAmount, setPayoutAmount] = useState("");
  const [preview, setPreview] = useState<AssessmentPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [description, setDescription] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<string>("");

  useEffect(() => {
    adminGetSettings()
      .then((s) => {
        setSettings(s);
        setEntranceFee((s.entrance_fee_cents / 100).toFixed(2));
        setMaintenanceFee((s.maintenance_fee_cents / 100).toFixed(2));
        setDuesAmount((s.maintenance_fee_cents / 100).toFixed(2));
        setAnchorMonth(String(s.maintenance_fee_anchor_month));
        setDueDays(String(s.assessment_due_days));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSaveFees(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg("");
    try {
      await adminUpdateSettings({
        entrance_fee_cents: Math.round(parseFloat(entranceFee) * 100),
        maintenance_fee_cents: Math.round(parseFloat(maintenanceFee) * 100),
        maintenance_fee_anchor_month: parseInt(anchorMonth),
        assessment_due_days: parseInt(dueDays),
      });
      setSaveMsg("Settings saved.");
      const refreshed = await adminGetSettings();
      setSettings(refreshed);
    } catch (err) {
      setSaveMsg(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerateDues(e: React.FormEvent) {
    e.preventDefault();
    const amount_cents = Math.round(parseFloat(duesAmount) * 100);
    if (!amount_cents || amount_cents <= 0) { setDuesResult("Enter a valid amount."); return; }
    if (!confirm(`Generate ${duesYear} annual dues of $${duesAmount} for all active members who don't yet have a dues obligation for ${duesYear}?`)) return;
    setDuesLoading(true);
    setDuesResult("");
    try {
      const r = await adminGenerateAnnualDues({ year: parseInt(duesYear), amount_cents, due_date: duesDueDate });
      setDuesResult(`Done: ${r.created} obligations created, ${r.skipped} members already billed.`);
    } catch (err) {
      setDuesResult(err instanceof ApiError ? err.message : "Failed.");
    } finally {
      setDuesLoading(false);
    }
  }

  async function handlePreview() {
    const dollars = parseFloat(payoutAmount);
    if (!dollars || dollars <= 0) {
      setPreviewError("Enter a valid payout amount.");
      return;
    }
    setPreviewLoading(true);
    setPreviewError("");
    setPreview(null);
    try {
      const result = await adminAssessmentPreview(dollars);
      setPreview(result);
    } catch (err) {
      setPreviewError(err instanceof ApiError ? err.message : "Preview failed.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleProcessAssessment() {
    if (!preview) return;
    setProcessing(true);
    try {
      const result = await adminProcessAssessment({
        total_cents: preview.total_payout_cents,
        per_member_cents: preview.per_member_cents,
        due_date: preview.due_date,
        description: description || "Special Assessment",
      });
      setProcessResult(
        `Assessment created: ${result.member_count} members assessed ${formatMoney(result.per_member_cents)} each, due ${formatDate(result.due_date)}.`
      );
      setShowConfirm(false);
      setPreview(null);
      setPayoutAmount("");
      setDescription("");
    } catch (err) {
      setProcessResult(err instanceof ApiError ? err.message : "Processing failed.");
    } finally {
      setProcessing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {settings?.active_member_count ?? "—"} active members
        </p>
      </div>

      {/* ── Membership Fees ── */}
      <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Membership Fees</h2>
        <form onSubmit={handleSaveFees} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Initial Entrance Fee ($)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={entranceFee}
                onChange={(e) => setEntranceFee(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
              <p className="text-xs text-gray-400 mt-1">Charged when a new member joins</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Annual Maintenance Fee ($)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={maintenanceFee}
                onChange={(e) => setMaintenanceFee(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
              <p className="text-xs text-gray-400 mt-1">Annual renewal cost</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Annual Billing Month
              </label>
              <select
                value={anchorMonth}
                onChange={(e) => setAnchorMonth(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                {MONTH_NAMES.slice(1).map((name, i) => (
                  <option key={i + 1} value={i + 1}>{name}</option>
                ))}
              </select>
              <p className="text-xs text-gray-400 mt-1">Annual dues billing cycle start</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Assessment Due Period (days)
              </label>
              <input
                type="number"
                min="1"
                max="365"
                value={dueDays}
                onChange={(e) => setDueDays(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              />
              <p className="text-xs text-gray-400 mt-1">Days from assessment to payment due date</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="bg-green-700 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-green-800 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save Settings"}
            </button>
            {saveMsg && (
              <p className={`text-sm ${saveMsg.includes("saved") ? "text-green-700" : "text-red-600"}`}>
                {saveMsg}
              </p>
            )}
          </div>
        </form>
      </section>

      {/* ── Annual Dues Generation ── */}
      <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-1">Generate Annual Dues</h2>
        <p className="text-sm text-gray-500 mb-4">
          Create a fixed dues obligation for every active member who doesn't already have one for the selected year.
          Members who have already paid will have their payment auto-applied when recorded.
        </p>
        <form onSubmit={handleGenerateDues} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Year</label>
              <select
                value={duesYear}
                onChange={(e) => { setDuesYear(e.target.value); setDuesDueDate(`${e.target.value}-12-31`); }}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                {[2024, 2025, 2026].map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Amount Per Member ($)</label>
              <input
                type="number" min="0" step="0.01"
                value={duesAmount}
                onChange={(e) => setDuesAmount(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Due Date</label>
              <input
                type="date"
                value={duesDueDate}
                onChange={(e) => setDuesDueDate(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={duesLoading}
              className="bg-green-700 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-green-800 disabled:opacity-50"
            >
              {duesLoading ? "Generating…" : `Generate ${duesYear} Annual Dues`}
            </button>
            {duesResult && (
              <p className={`text-sm ${duesResult.includes("Done") ? "text-green-700" : "text-red-600"}`}>
                {duesResult}
              </p>
            )}
          </div>
        </form>
      </section>

      {/* ── Special Assessment Calculator ── */}
      <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-1">Special Assessment Calculator</h2>
        <p className="text-sm text-gray-500 mb-4">
          Calculate and issue a per-member fee based on a total payout amount.
        </p>

        <div className="bg-gray-50 rounded-xl p-4 mb-4 text-sm text-gray-600 space-y-1">
          <p>Active Members (live count): <span className="font-semibold text-gray-900">{settings?.active_member_count ?? "—"}</span></p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Total Payout Amount ($)
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="e.g. 15000"
              value={payoutAmount}
              onChange={(e) => { setPayoutAmount(e.target.value); setPreview(null); setPreviewError(""); }}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Description (shown on member statements)
            </label>
            <input
              type="text"
              placeholder="e.g. Bereavement Assessment — Doe Family"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>

          <button
            onClick={handlePreview}
            disabled={previewLoading || !payoutAmount}
            className="bg-blue-600 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {previewLoading ? "Calculating…" : "Preview Assessment"}
          </button>

          {previewError && (
            <p className="text-sm text-red-600">{previewError}</p>
          )}

          {preview && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
              <p className="text-sm font-semibold text-amber-900">Assessment Preview</p>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-xl font-bold text-gray-900">{preview.active_member_count}</p>
                  <p className="text-xs text-gray-500">Active Members</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-gray-900">{formatMoney(preview.per_member_cents)}</p>
                  <p className="text-xs text-gray-500">Per Member</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-gray-900">{formatMoney(preview.total_payout_cents)}</p>
                  <p className="text-xs text-gray-500">Total Payout</p>
                </div>
              </div>
              <p className="text-xs text-gray-600 italic">
                You are about to assess {preview.active_member_count} members{" "}
                {formatMoney(preview.per_member_cents)} each to cover a total payout of{" "}
                {formatMoney(preview.total_payout_cents)}, due by {formatDate(preview.due_date)}.
              </p>
              <button
                onClick={() => setShowConfirm(true)}
                className="w-full bg-red-600 text-white text-sm font-semibold py-2 rounded-lg hover:bg-red-700"
              >
                Process Assessment
              </button>
            </div>
          )}

          {processResult && (
            <div className={`rounded-xl px-4 py-3 text-sm ${processResult.includes("created") ? "bg-green-50 text-green-800" : "bg-red-50 text-red-700"}`}>
              {processResult}
            </div>
          )}
        </div>
      </section>

      {/* ── Audit Log ── */}
      {settings && settings.audit_log.length > 0 && (
        <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Settings Change Log</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-100 text-xs text-gray-500 uppercase">
                  <th className="pb-2 pr-4">Field</th>
                  <th className="pb-2 pr-4">Old</th>
                  <th className="pb-2 pr-4">New</th>
                  <th className="pb-2 pr-4">Changed By</th>
                  <th className="pb-2">When</th>
                </tr>
              </thead>
              <tbody>
                {settings.audit_log.map((log, i) => (
                  <tr key={i} className="border-b border-gray-50 last:border-0">
                    <td className="py-2 pr-4 font-mono text-xs text-gray-700">{log.field}</td>
                    <td className="py-2 pr-4 text-gray-500">{log.old_value}</td>
                    <td className="py-2 pr-4 font-medium">{log.new_value}</td>
                    <td className="py-2 pr-4 text-gray-600">{log.changed_by}</td>
                    <td className="py-2 text-gray-400 text-xs">{new Date(log.changed_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Confirmation Modal ── */}
      {showConfirm && preview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-900">Confirm Assessment</h3>
            <p className="text-sm text-gray-700">
              You are about to assess{" "}
              <span className="font-semibold">{preview.active_member_count} members</span> a fee of{" "}
              <span className="font-semibold">{formatMoney(preview.per_member_cents)}</span> each to
              cover a total payout of{" "}
              <span className="font-semibold">{formatMoney(preview.total_payout_cents)}</span>.
            </p>
            {description && (
              <p className="text-xs text-gray-500">Description: {description}</p>
            )}
            <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
              This will create {preview.active_member_count} new obligation records. This action cannot be undone automatically.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                disabled={processing}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleProcessAssessment}
                disabled={processing}
                className="px-4 py-2 text-sm bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {processing ? "Processing…" : "Yes, Proceed"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
