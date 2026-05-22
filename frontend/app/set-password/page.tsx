"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// apiFetch is not exported — add a thin wrapper here
async function setPassword(uid: string, token: string, password: string) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/auth/set-password/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid, token, password }),
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? "Failed to set password.");
  }
  return res.json();
}

function SetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const uid = params.get("uid") ?? "";
  const token = params.get("token") ?? "";

  const [password, setPasswordValue] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }
    setLoading(true);
    try {
      await setPassword(uid, token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  if (!uid || !token) {
    return (
      <p className="text-sm text-red-600">
        Invalid or missing invite link. Please contact your administrator.
      </p>
    );
  }

  if (done) {
    return (
      <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
        Password set! Redirecting to login…
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="New password"
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPasswordValue(e.target.value)}
        required
        disabled={loading}
      />
      <Input
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        required
        disabled={loading}
        error={confirm && password !== confirm ? "Passwords do not match" : undefined}
      />
      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}
      <Button type="submit" loading={loading} className="w-full mt-2">
        Set password &amp; activate account
      </Button>
    </form>
  );
}

export default function SetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-green-800">Addis Kidan</h1>
          <p className="text-sm text-gray-500 mt-1">Activate your account</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Set your password</h2>
          <p className="text-sm text-gray-500 mb-6">
            Choose a password to complete your account setup.
          </p>
          <Suspense>
            <SetPasswordForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
