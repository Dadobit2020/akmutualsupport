"use client";

import { useEffect, useState } from "react";
import { getMyObligations, getMyPayments, downloadReceipt, Obligation, Payment, ApiError } from "@/lib/api";
import { formatMoney, formatDate, STATUS_LABELS, STATUS_COLORS } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Tab = "open" | "all" | "payments";

export default function ObligationsPage() {
  const [tab, setTab] = useState<Tab>("open");
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        if (tab === "payments") {
          const data = await getMyPayments();
          setPayments(data);
        } else {
          const params: Record<string, string> =
            tab === "open" ? { status: "open,partially_paid" } : {};
          const data = await getMyObligations(params);
          setObligations(data);
        }
      } catch (err) {
        if (err instanceof ApiError) setError(err.message);
        else setError("Failed to load data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tab]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Contributions</h1>
        <p className="text-sm text-gray-500 mt-0.5">Your contribution history and outstanding amounts</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
        {(["open", "all", "payments"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-sm font-medium rounded-lg transition-colors ${
              tab === t ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "open" ? "Open" : t === "all" ? "All" : "Payments"}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-7 w-7 border-2 border-green-700 border-t-transparent" />
        </div>
      ) : tab === "payments" ? (
        <PaymentsList payments={payments} />
      ) : (
        <ObligationsList obligations={obligations} />
      )}
    </div>
  );
}

function ObligationsList({ obligations }: { obligations: Obligation[] }) {
  if (obligations.length === 0) {
    return (
      <Card>
        <p className="text-sm text-gray-500 text-center py-8">No contributions found.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {obligations.map((o) => {
        const isOverdue = o.status !== "paid" && o.status !== "waived" && new Date(o.due_date) < new Date();
        return (
          <Card key={o.id} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {o.event_description ?? "Recurring dues"}
                </p>
                <p className={`text-xs mt-1 ${isOverdue ? "text-red-600 font-medium" : "text-gray-400"}`}>
                  Due {formatDate(o.due_date)}{isOverdue ? " · Overdue" : ""}
                </p>
                {o.paid_cents > 0 && o.status !== "paid" && (
                  <p className="text-xs text-green-600 mt-0.5">
                    {formatMoney(o.paid_cents)} paid of {formatMoney(o.amount_cents)}
                  </p>
                )}
                {o.waiver_reason && (
                  <p className="text-xs text-gray-400 mt-0.5 italic">Waived: {o.waiver_reason}</p>
                )}
              </div>
              <div className="text-right shrink-0 space-y-1.5">
                <p className="text-sm font-bold text-gray-900">
                  {o.status === "paid" ? formatMoney(o.amount_cents) : formatMoney(o.outstanding_cents)}
                </p>
                <Badge
                  label={STATUS_LABELS[o.status] ?? o.status}
                  colorClass={STATUS_COLORS[o.status]}
                />
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function PaymentsList({ payments }: { payments: Payment[] }) {
  const [downloading, setDownloading] = useState<string | null>(null);

  async function handleDownload(paymentId: string) {
    setDownloading(paymentId);
    try {
      await downloadReceipt(paymentId);
    } finally {
      setDownloading(null);
    }
  }

  if (payments.length === 0) {
    return (
      <Card>
        <p className="text-sm text-gray-500 text-center py-8">No payments recorded yet.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {payments.map((p) => (
        <Card key={p.id} className="p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-900">{formatMoney(p.amount_cents)}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {formatDate(p.payment_date)} · {p.method.replace("_", " ")}
                {p.reference ? ` · Ref: ${p.reference}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Received
              </span>
              <button
                onClick={() => handleDownload(p.id)}
                disabled={downloading === p.id}
                className="text-xs text-green-700 hover:text-green-900 font-medium disabled:opacity-50"
              >
                {downloading === p.id ? "…" : "PDF"}
              </button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
