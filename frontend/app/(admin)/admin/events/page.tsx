"use client";

import { useEffect, useState, useCallback } from "react";
import {
  adminEvents,
  adminCreateEvent,
  AdminEvent,
  ApiError,
} from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const EVENT_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  pending_approval: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-700",
  obligations_generated: "bg-blue-100 text-blue-800",
  collecting: "bg-purple-100 text-purple-800",
  closed: "bg-green-100 text-green-800",
  reversed: "bg-gray-100 text-gray-500",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  bereavement: "Bereavement",
  medical_emergency: "Medical Emergency",
  other: "Other",
};

function CreateEventModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    event_type: "bereavement",
    household_name: "",
    event_date: new Date().toISOString().split("T")[0],
    payout_amount_dollars: "",
    description: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payout_amount_cents = Math.round(parseFloat(form.payout_amount_dollars) * 100);
    if (isNaN(payout_amount_cents) || payout_amount_cents <= 0) {
      setError("Enter a valid payout amount.");
      return;
    }
    if (!form.household_name.trim()) {
      setError("Household name is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await adminCreateEvent({
        event_type: form.event_type,
        household_name: form.household_name.trim(),
        event_date: form.event_date,
        payout_amount_cents,
        description: form.description,
      });
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to create event.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Create Event</h2>
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

          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Event Type</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
              value={form.event_type}
              onChange={(e) => setForm({ ...form, event_type: e.target.value })}
            >
              <option value="bereavement">Bereavement</option>
              <option value="medical_emergency">Medical Emergency</option>
              <option value="other">Other</option>
            </select>
          </div>

          <Input
            label="Household Name"
            placeholder="e.g. Tesfaye Family"
            value={form.household_name}
            onChange={(e) => setForm({ ...form, household_name: e.target.value })}
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Event Date"
              type="date"
              value={form.event_date}
              onChange={(e) => setForm({ ...form, event_date: e.target.value })}
              required
            />
            <Input
              label="Payout Amount (USD)"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="0.00"
              value={form.payout_amount_dollars}
              onChange={(e) => setForm({ ...form, payout_amount_dollars: e.target.value })}
              required
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Description</label>
            <textarea
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600 resize-none"
              rows={3}
              placeholder="Brief description of the event..."
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Create Event
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function EventsPage() {
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await adminEvents({ page: String(page) });
      setEvents(res.results);
      setTotal(res.count);
      setTotalPages(res.total_pages);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load events.");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Events</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} total events</p>
        </div>
        <Button onClick={() => setShowModal(true)}>Create Event</Button>
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
        ) : events.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-12">No events found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Household</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Event Date</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Payout</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {events.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-900">
                      {EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{e.household}</td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(e.event_date)}</td>
                    <td className="px-4 py-3 text-right text-gray-700 font-semibold">
                      {formatMoney(e.payout_amount_cents)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        label={e.status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        colorClass={EVENT_STATUS_COLORS[e.status] ?? "bg-gray-100 text-gray-600"}
                      />
                    </td>
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
        <CreateEventModal
          onClose={() => setShowModal(false)}
          onCreated={() => { setShowModal(false); load(); }}
        />
      )}
    </div>
  );
}
