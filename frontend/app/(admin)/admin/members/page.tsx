"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  adminMembers,
  adminCreateMember,
  adminUpdateMember,
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

const STATUS_TABS = [
  { value: "", label: "All" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "suspended", label: "Suspended" },
];

function AddMemberModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (m: AdminMember) => void;
}) {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    join_date: new Date().toISOString().split("T")[0],
    status: "active",
    tier: "standard",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const member = await adminCreateMember(form);
      onCreated(member);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to create member.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Add New Member</h2>
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
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="First Name"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              required
            />
            <Input
              label="Last Name"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              required
            />
          </div>
          <Input
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <Input
            label="Phone"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
          <Input
            label="Join Date"
            type="date"
            value={form.join_date}
            onChange={(e) => setForm({ ...form, join_date: e.target.value })}
            required
          />
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Status</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Tier</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
                value={form.tier}
                onChange={(e) => setForm({ ...form, tier: e.target.value })}
              >
                <option value="standard">Standard</option>
                <option value="senior">Senior</option>
                <option value="family">Family</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Add Member
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function MembersPage() {
  const [members, setMembers] = useState<AdminMember[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [statusChanging, setStatusChanging] = useState<string | null>(null);

  async function handleStatusChange(m: AdminMember, newStatus: string) {
    if (!confirm(`${newStatus === "suspended" ? "Suspend" : "Activate"} ${m.first_name} ${m.last_name}?`)) return;
    setStatusChanging(m.id);
    try {
      const updated = await adminUpdateMember(m.id, { status: newStatus });
      setMembers((prev) => prev.map((x) => x.id === m.id ? { ...x, status: updated.status } : x));
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed.");
    } finally {
      setStatusChanging(null);
    }
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = { page: String(page) };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const res = await adminMembers(params);
      setMembers(res.results);
      setTotal(res.count);
      setTotalPages(res.total_pages);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load members.");
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, statusFilter]);

  return (
    <div className="space-y-5 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Members</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} total members</p>
        </div>
        <Button onClick={() => setShowAdd(true)}>Add Member</Button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <Input
            placeholder="Search by name, email, or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={`px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                statusFilter === tab.value
                  ? "bg-green-700 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
          </div>
        ) : members.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-12">No members found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Phone</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Email</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Join Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Outstanding</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {members.map((m) => (
                  <tr key={m.id} className="hover:bg-gray-50 group">
                    <td className="px-5 py-3">
                      <Link
                        href={`/admin/members/${m.id}`}
                        className="font-medium text-gray-900 group-hover:text-green-700"
                      >
                        {m.first_name} {m.last_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{m.phone || "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{m.email || "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(m.join_date)}</td>
                    <td className="px-4 py-3">
                      <Badge
                        label={m.status.charAt(0).toUpperCase() + m.status.slice(1)}
                        colorClass={STATUS_COLORS[m.status] ?? "bg-gray-100 text-gray-600"}
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={m.outstanding_cents > 0 ? "text-amber-700 font-semibold" : "text-green-700"}>
                        {formatMoney(m.outstanding_cents)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-3">
                        {m.status === "active" && (
                          <button
                            onClick={() => handleStatusChange(m, "suspended")}
                            disabled={statusChanging === m.id}
                            className="text-xs text-amber-600 hover:underline disabled:opacity-40"
                          >
                            Suspend
                          </button>
                        )}
                        {m.status === "suspended" && (
                          <button
                            onClick={() => handleStatusChange(m, "active")}
                            disabled={statusChanging === m.id}
                            className="text-xs text-green-700 hover:underline disabled:opacity-40"
                          >
                            Activate
                          </button>
                        )}
                        <Link
                          href={`/admin/members/${m.id}`}
                          className="text-xs text-green-700 hover:underline font-medium"
                        >
                          View
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Page {page} of {totalPages} ({total} members)
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {showAdd && (
        <AddMemberModal
          onClose={() => setShowAdd(false)}
          onCreated={(m) => {
            setShowAdd(false);
            load();
          }}
        />
      )}
    </div>
  );
}
