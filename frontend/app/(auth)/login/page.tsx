"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { login, saveTokens, ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState("");
  const [needsMfa, setNeedsMfa] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await login({
        email,
        password,
        ...(needsMfa ? { mfa_token: mfaToken } : {}),
      });
      saveTokens(result.access, result.refresh);
      await refresh();
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail;
        if (
          typeof detail === "object" &&
          detail !== null &&
          "mfa_token" in detail
        ) {
          setNeedsMfa(true);
          setError("Please enter your authenticator code.");
        } else {
          setError(typeof detail === "string" ? detail : "Login failed. Please check your credentials.");
        }
      } else {
        setError("Unable to connect. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-3">
            <Image
              src="/logo.png"
              alt="AKMSA"
              width={72}
              height={72}
              className="rounded-full object-contain"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
          </div>
          <h1 className="text-2xl font-bold text-green-800">AKMSA</h1>
          <p className="text-sm text-gray-500 mt-1">Member Portal</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Sign in to your account</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              id="email"
              label="Email address"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
            />
            <Input
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />

            {needsMfa && (
              <Input
                id="mfa_token"
                label="Authenticator code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="6-digit code"
                value={mfaToken}
                onChange={(e) => setMfaToken(e.target.value)}
                required
                disabled={loading}
                autoFocus
              />
            )}

            {error && (
              <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
            )}

            <Button type="submit" loading={loading} className="w-full mt-2">
              {needsMfa ? "Verify & sign in" : "Sign in"}
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          Having trouble? Contact your association administrator.
        </p>
      </div>
    </div>
  );
}
