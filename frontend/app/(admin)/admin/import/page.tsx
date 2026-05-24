"use client";

import { useRef, useState } from "react";
import { formatMoney, formatDate } from "@/lib/utils";
import { getAccessToken, refreshAccessToken, ApiError } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type TxnStatus = "matched" | "unmatched" | "duplicate";

interface ParsedTxn {
  idx: number;
  txn_type: string;
  date: string;
  member_name: string;
  matched_member_id: string | null;
  matched_member_name: string | null;
  amount_cents: number;
  description: string;
  reference: string;
  method: string;
  status: TxnStatus;
  include: boolean;
}

interface ParseResult {
  filename: string;
  total: number;
  matched: number;
  unmatched: number;
  duplicate: number;
  transactions: ParsedTxn[];
}

const STATUS_STYLE: Record<TxnStatus, string> = {
  matched: "bg-green-100 text-green-800",
  unmatched: "bg-amber-100 text-amber-800",
  duplicate: "bg-gray-100 text-gray-500",
};

async function apiFetchMultipart<T>(path: string, body: FormData): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", headers, body });
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) return apiFetchMultipart<T>(path, body);
    throw new ApiError(401, "Session expired.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err?.error ?? err?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiPost<T>(path: string, data: object): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", headers, body: JSON.stringify(data) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err?.error ?? err?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export default function ImportPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [parseError, setParsError] = useState("");
  const [result, setResult] = useState<ParseResult | null>(null);
  const [txns, setTxns] = useState<ParsedTxn[]>([]);
  const [processing, setProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<{ recorded: number; skipped_duplicate: number; skipped_no_member: number; errors: string[] } | null>(null);

  async function handleFile(file: File) {
    setParsError("");
    setResult(null);
    setTxns([]);
    setProcessResult(null);
    setParsing(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const data = await apiFetchMultipart<ParseResult>("/admin/import/parse/", form);
      setResult(data);
      setTxns(data.transactions);
    } catch (err) {
      setParsError(err instanceof ApiError ? String(err.detail) : "Failed to parse file.");
    } finally {
      setParsing(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }

  function toggleInclude(idx: number) {
    setTxns((prev) => prev.map((t) => t.idx === idx ? { ...t, include: !t.include } : t));
  }

  function selectAll(include: boolean) {
    setTxns((prev) => prev.map((t) => t.status === "matched" ? { ...t, include } : t));
  }

  async function handleProcess() {
    const toImport = txns.filter((t) => t.include);
    if (!toImport.length) return;
    if (!confirm(`Import ${toImport.length} payment(s)? This cannot be automatically reversed.`)) return;
    setProcessing(true);
    setProcessResult(null);
    try {
      const res = await apiPost<{ recorded: number; skipped_duplicate: number; skipped_no_member: number; errors: string[] }>(
        "/admin/import/process/",
        { transactions: toImport }
      );
      setProcessResult(res);
      // Remove imported rows from preview
      setTxns((prev) => prev.map((t) => t.include ? { ...t, status: "duplicate" as TxnStatus, include: false } : t));
    } catch (err) {
      setParsError(err instanceof ApiError ? String(err.detail) : "Import failed.");
    } finally {
      setProcessing(false);
    }
  }

  const selectedCount = txns.filter((t) => t.include).length;
  const selectedCents = txns.filter((t) => t.include).reduce((s, t) => s + t.amount_cents, 0);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Import Statements</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Upload a Wells Fargo bank statement PDF or a Tithe.ly Excel/CSV export to import payments.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-colors ${
          dragOver ? "border-green-500 bg-green-50" : "border-gray-200 hover:border-green-400 hover:bg-gray-50"
        }`}
      >
        <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls,.csv" className="hidden" onChange={onFileChange} />
        {parsing ? (
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-green-700 border-t-transparent" />
            <p className="text-sm text-gray-600">Parsing file…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <svg className="w-10 h-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <p className="text-sm font-medium text-gray-700">Drop file here or click to browse</p>
            <p className="text-xs text-gray-400">Wells Fargo PDF · Tithe.ly XLSX / CSV</p>
          </div>
        )}
      </div>

      {parseError && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {parseError}
        </div>
      )}

      {/* Process result */}
      {processResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-4 text-sm text-green-800 space-y-1">
          <p className="font-semibold">Import complete</p>
          <p>Recorded: <strong>{processResult.recorded}</strong> payments</p>
          {processResult.skipped_duplicate > 0 && <p>Skipped (already recorded): {processResult.skipped_duplicate}</p>}
          {processResult.skipped_no_member > 0 && <p>Skipped (no member match): {processResult.skipped_no_member}</p>}
          {processResult.errors.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-red-700 font-medium">{processResult.errors.length} error(s)</summary>
              <ul className="mt-1 space-y-0.5 text-xs text-red-600">
                {processResult.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Preview */}
      {result && txns.length > 0 && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-6 items-center">
            <div className="text-center">
              <p className="text-xl font-bold text-gray-900">{result.total}</p>
              <p className="text-xs text-gray-500">Total found</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-green-700">{result.matched}</p>
              <p className="text-xs text-gray-500">Matched</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-amber-600">{result.unmatched}</p>
              <p className="text-xs text-gray-500">Unmatched</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-gray-400">{result.duplicate}</p>
              <p className="text-xs text-gray-500">Already recorded</p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <button onClick={() => selectAll(true)}
                className="text-xs text-green-700 underline underline-offset-2">Select all matched</button>
              <button onClick={() => selectAll(false)}
                className="text-xs text-gray-500 underline underline-offset-2">Deselect all</button>
            </div>
          </div>

          {/* Transaction table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 w-10" />
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Date</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">From (bank)</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Matched Member</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Amount</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {txns.map((t) => (
                    <tr key={t.idx}
                      className={`${t.status === "duplicate" ? "opacity-40" : "hover:bg-gray-50"} ${t.include ? "bg-green-50/40" : ""}`}>
                      <td className="px-4 py-3">
                        {t.status !== "duplicate" && (
                          <input type="checkbox" checked={t.include}
                            onChange={() => toggleInclude(t.idx)}
                            className="w-4 h-4 accent-green-700 cursor-pointer" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{formatDate(t.date)}</td>
                      <td className="px-4 py-3 text-gray-700">{t.member_name || <span className="text-gray-300 italic">—</span>}</td>
                      <td className="px-4 py-3">
                        {t.matched_member_name
                          ? <span className="font-medium text-gray-900">{t.matched_member_name}</span>
                          : <span className="text-amber-600 text-xs italic">no match</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-gray-800 whitespace-nowrap">
                        {formatMoney(t.amount_cents)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLE[t.status]}`}>
                          {t.status === "duplicate" ? "already recorded" : t.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Import bar */}
          <div className="sticky bottom-0 bg-white border border-gray-200 rounded-2xl shadow-lg px-5 py-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-gray-800">
                {selectedCount} payment{selectedCount !== 1 ? "s" : ""} selected — {formatMoney(selectedCents)}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                Unmatched rows will not be imported — record them manually via Payments.
              </p>
            </div>
            <button
              onClick={handleProcess}
              disabled={processing || selectedCount === 0}
              className="bg-green-700 text-white text-sm font-semibold px-6 py-2.5 rounded-xl hover:bg-green-800 disabled:opacity-40"
            >
              {processing ? "Importing…" : `Import ${selectedCount} Payment${selectedCount !== 1 ? "s" : ""}`}
            </button>
          </div>
        </div>
      )}

      {result && txns.length === 0 && (
        <p className="text-sm text-gray-500 text-center py-8">No importable transactions found in this file.</p>
      )}
    </div>
  );
}
