"use client";

import { useEffect, useState } from "react";
import {
  adminDashboard,
  AdminDashboard,
  ApiError,
} from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";

function MetricCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${accent ?? "text-gray-900"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

const METHOD_LABELS: Record<string, string> = {
  check: "Check",
  bank_transfer: "Bank Transfer",
  cash: "Cash",
  online: "Online",
  other: "Other",
};

export default function AdminDashboardPage() {
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    adminDashboard()
      .then(setData)
      .catch((err) => {
        if (err instanceof ApiError) setError(err.message);
        else setError("Failed to load dashboard.");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!data) return null;

  const obligationStatuses = Object.entries(data.obligations_by_status);

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Association Overview</h1>
        <p className="text-sm text-gray-500 mt-0.5">Real-time summary of membership, finances, and obligations</p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricCard
          label="Total Members"
          value={String(data.total_members)}
          sub={`${data.members_this_month} joined this month`}
        />
        <MetricCard
          label="Active Members"
          value={String(data.active_members)}
          sub={`${data.total_members - data.active_members} inactive`}
          accent="text-green-700"
        />
        <MetricCard
          label="Total Collected"
          value={formatMoney(data.total_collected_cents)}
          sub="all time contributions"
          accent="text-green-700"
        />
        <MetricCard
          label="Outstanding Balance"
          value={formatMoney(data.outstanding_cents)}
          sub="unpaid obligations"
          accent={data.outstanding_cents > 0 ? "text-amber-700" : "text-green-700"}
        />
        <MetricCard
          label="Total Payouts"
          value={formatMoney(data.total_payouts_cents)}
          sub="disbursed to households"
        />
        <MetricCard
          label="New This Month"
          value={String(data.members_this_month)}
          sub="new members"
          accent="text-blue-700"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Payments */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-800">Recent Payments</h2>
            </div>
            {data.recent_payments.length === 0 ? (
              <p className="text-sm text-gray-500 px-5 py-6 text-center">No payments recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Member</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Method</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {data.recent_payments.map((p) => (
                      <tr key={p.id} className="hover:bg-gray-50">
                        <td className="px-5 py-3 font-medium text-gray-900">{p.member_name}</td>
                        <td className="px-4 py-3 text-green-700 font-semibold">{formatMoney(p.amount_cents)}</td>
                        <td className="px-4 py-3 text-gray-500">{formatDate(p.payment_date)}</td>
                        <td className="px-4 py-3 text-gray-500">{METHOD_LABELS[p.method] ?? p.method}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Obligations breakdown */}
        <div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-800">Obligations by Status</h2>
            </div>
            <div className="px-5 py-4 space-y-3">
              {obligationStatuses.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-2">No obligations found.</p>
              ) : (
                obligationStatuses.map(([s, count]) => (
                  <div key={s} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 capitalize">{s.replace("_", " ")}</span>
                    <span className={`text-sm font-bold ${
                      s === "paid" ? "text-green-700"
                        : s === "open" ? "text-amber-700"
                        : s === "partially_paid" ? "text-blue-700"
                        : "text-gray-500"
                    }`}>
                      {count}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
