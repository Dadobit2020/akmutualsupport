"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { getMyObligations, getMyBalance, getDashboard, Obligation, MemberBalance, DashboardData, ApiError } from "@/lib/api";
import { formatMoney, formatDate, STATUS_LABELS, STATUS_COLORS } from "@/lib/utils";
import { Card, CardTitle, CardValue } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { user } = useAuth();
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [balance, setBalance] = useState<MemberBalance | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [oblData, balData] = await Promise.all([
          getMyObligations({ status: "open,partially_paid" }),
          getMyBalance().catch(() => null),
        ]);
        setObligations(oblData.slice(0, 5));
        setBalance(balData);
        // Try to load admin dashboard too (only works for admin users)
        try {
          const dash = await getDashboard();
          setDashboard(dash);
        } catch {
          // Non-admin users get 403 — that's fine
        }
      } catch (err) {
        if (err instanceof ApiError) setError(err.message);
        else setError("Failed to load data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const totalOutstanding = balance?.outstanding_cents ?? obligations.reduce((sum, o) => sum + o.outstanding_cents, 0);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">
          Welcome, {user?.first_name}
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">Here's your account overview</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Balance summary */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card>
          <CardTitle>Outstanding balance</CardTitle>
          <CardValue className={totalOutstanding > 0 ? "text-amber-700" : "text-green-700"}>
            {formatMoney(totalOutstanding)}
          </CardValue>
          {totalOutstanding === 0 && (
            <p className="text-xs text-green-600 mt-1">All contributions up to date</p>
          )}
        </Card>

        <Card>
          <CardTitle>Open contributions</CardTitle>
          <CardValue>{balance?.open_obligation_count ?? obligations.length}</CardValue>
          <p className="text-xs text-gray-500 mt-1">awaiting payment</p>
        </Card>
      </div>

      {/* Admin stats (only shown to admins) */}
      {dashboard && (
        <Card className="bg-green-50 border-green-100">
          <p className="text-xs font-semibold text-green-800 uppercase tracking-wide mb-3">Association overview</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Stat label="Total outstanding" value={formatMoney(dashboard.outstanding_cents)} />
            <Stat label="Active events" value={String(dashboard.active_events)} />
            <Stat label="Review queue" value={String(dashboard.reconciliation_review_queue)} />
            <Stat label="Active members" value={String(dashboard.active_members)} />
          </div>
        </Card>
      )}

      {/* Open obligations */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-800">Open contributions</h2>
          <Link href="/obligations">
            <Button variant="ghost" className="text-xs">View all</Button>
          </Link>
        </div>

        {obligations.length === 0 ? (
          <Card>
            <p className="text-sm text-gray-500 text-center py-4">
              No open contributions — you're all caught up!
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {obligations.map((o) => (
              <ObligationRow key={o.id} obligation={o} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ObligationRow({ obligation: o }: { obligation: Obligation }) {
  const isOverdue = new Date(o.due_date) < new Date();
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 truncate">
            {o.event_description ?? "Recurring dues"}
          </p>
          <p className={`text-xs mt-0.5 ${isOverdue ? "text-red-600 font-medium" : "text-gray-500"}`}>
            Due {formatDate(o.due_date)}{isOverdue ? " — overdue" : ""}
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-sm font-bold text-gray-900">{formatMoney(o.outstanding_cents)}</p>
          <Badge
            label={STATUS_LABELS[o.status] ?? o.status}
            colorClass={STATUS_COLORS[o.status]}
          />
        </div>
      </div>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-lg font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}
