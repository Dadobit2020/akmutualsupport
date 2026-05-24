"use client";

import { useEffect, useState, useCallback } from "react";
import { adminActivityLog, ActivityLogEntry, ApiError } from "@/lib/api";

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  payment_recorded:   { label: "Payment Recorded",    color: "bg-green-100 text-green-800" },
  payment_deleted:    { label: "Payment Voided",       color: "bg-red-100 text-red-700" },
  member_created:     { label: "Member Added",         color: "bg-blue-100 text-blue-800" },
  member_updated:     { label: "Member Updated",       color: "bg-gray-100 text-gray-700" },
  member_suspended:   { label: "Member Suspended",     color: "bg-amber-100 text-amber-800" },
  member_activated:   { label: "Member Activated",     color: "bg-green-100 text-green-800" },
  member_deactivated: { label: "Member Deactivated",   color: "bg-gray-100 text-gray-600" },
  member_left:        { label: "Member Left",          color: "bg-gray-100 text-gray-600" },
  member_status_changed: { label: "Status Changed",   color: "bg-amber-100 text-amber-700" },
};

const ACTION_FILTERS = [
  { value: "", label: "All Actions" },
  { value: "payment_recorded", label: "Payments" },
  { value: "payment_deleted", label: "Voided" },
  { value: "member_created", label: "New Members" },
  { value: "member_suspended", label: "Suspensions" },
  { value: "member_activated", label: "Activations" },
];

function timeAgo(iso: string) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function ActivityPage() {
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = { page: String(page) };
      if (actionFilter) params.action = actionFilter;
      const res = await adminActivityLog(params);
      setEntries(res.results);
      setTotal(res.count);
      setTotalPages(res.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load activity.");
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [actionFilter]);

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Activity Log</h1>
        <p className="text-sm text-gray-500 mt-0.5">Every admin action — who did what and when</p>
      </div>

      {/* Filter bar */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-3 flex flex-wrap gap-2">
        {ACTION_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setActionFilter(f.value)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              actionFilter === f.value
                ? "bg-green-700 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-400 self-center">{total} entries</span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* Log entries */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-7 w-7 border-2 border-green-700 border-t-transparent" />
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-12">No activity recorded yet.</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {entries.map((e) => {
              const meta = ACTION_LABELS[e.action] ?? { label: e.action, color: "bg-gray-100 text-gray-600" };
              return (
                <div key={e.id} className="flex items-start gap-4 px-5 py-4 hover:bg-gray-50">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${meta.color}`}>
                        {meta.label}
                      </span>
                      {e.target_label && (
                        <span className="text-sm font-medium text-gray-800 truncate">{e.target_label}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-0.5">{e.description}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      <span className="font-medium text-gray-600">{e.actor}</span>
                      {e.actor_email && <span className="ml-1 text-gray-400">({e.actor_email})</span>}
                    </p>
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap mt-1">{timeAgo(e.created_at)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Page {page} of {totalPages}</p>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
              className="px-4 py-2 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50">
              Previous
            </button>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50">
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
