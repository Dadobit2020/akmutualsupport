"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  getCurrentUser,
  updateProfile,
  changePassword,
  downloadStatement,
  ApiError,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function ProfilePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Profile</h1>
        <p className="text-sm text-gray-500 mt-0.5">Update your contact information and account settings</p>
      </div>
      <ContactInfoForm />
      <StatementDownload />
      <PasswordForm />
    </div>
  );
}

// ── Statement download ─────────────────────────────────────────────────────────

function StatementDownload() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleDownload() {
    setLoading(true);
    setError("");
    try {
      await downloadStatement();
    } catch {
      setError("Could not download statement. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Account statement</h2>
          <p className="text-sm text-gray-500 mt-0.5">Download your full contribution and payment history as a PDF.</p>
          {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </div>
        <Button variant="secondary" loading={loading} onClick={handleDownload}>
          Download PDF
        </Button>
      </div>
    </Card>
  );
}

// ── Contact info ──────────────────────────────────────────────────────────────

function ContactInfoForm() {
  const { user, refresh } = useAuth();
  const [phone, setPhone] = useState("");
  const [phoneWhatsapp, setPhoneWhatsapp] = useState("");
  const [address, setAddress] = useState("");
  const [preferredLanguage, setPreferredLanguage] = useState("en");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [memberId, setMemberId] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const u = await getCurrentUser();
        // The user may have a linked member record via the API
        // Try to load extra contact fields from the member endpoint
        // (The user object itself only has email/name)
        setLoading(false);
      } catch {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess(false);
    try {
      // Update auth user profile (name fields)
      await updateProfile({
        first_name: (e.currentTarget as HTMLFormElement).first_name.value,
        last_name: (e.currentTarget as HTMLFormElement).last_name.value,
      });
      await refresh();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-100 rounded w-1/3" />
          <div className="h-9 bg-gray-100 rounded" />
          <div className="h-9 bg-gray-100 rounded" />
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-gray-900 mb-5">Contact information</h2>
      <form onSubmit={handleSave} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Input
            id="first_name"
            label="First name"
            defaultValue={user?.first_name ?? ""}
            required
          />
          <Input
            id="last_name"
            label="Last name"
            defaultValue={user?.last_name ?? ""}
            required
          />
        </div>
        <Input
          id="email"
          label="Email address"
          type="email"
          defaultValue={user?.email ?? ""}
          disabled
          className="bg-gray-50"
        />
        <p className="text-xs text-gray-400 -mt-2">
          To change your email address, contact your administrator.
        </p>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}
        {success && (
          <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
            Profile updated successfully.
          </p>
        )}

        <Button type="submit" loading={saving}>
          Save changes
        </Button>
      </form>
    </Card>
  );
}

// ── Password change ───────────────────────────────────────────────────────────

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);

    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    if (next.length < 12) {
      setError("New password must be at least 12 characters.");
      return;
    }

    setLoading(true);
    try {
      await changePassword(current, next);
      setSuccess(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to change password. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-gray-900 mb-5">Change password</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Current password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <Input
          label="New password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
        <Input
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          error={confirm && next !== confirm ? "Passwords do not match" : undefined}
        />

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}
        {success && (
          <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
            Password changed successfully.
          </p>
        )}

        <Button type="submit" loading={loading} variant="secondary">
          Update password
        </Button>
      </form>
    </Card>
  );
}
