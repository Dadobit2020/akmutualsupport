"use client";

export default function ImportPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Import Members & Payments</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Use management commands on Render to import data from CSV files.
        </p>
      </div>

      {/* Download template */}
      <div className="bg-green-50 border border-green-200 rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-green-900 mb-2">Download Import Templates</h2>
        <p className="text-sm text-green-700 mb-4">
          Download the CSV template below, fill it in with your member data, then upload it to the Render shell.
        </p>
        <a
          href="/member_import_template.csv"
          download
          className="inline-flex items-center gap-2 px-4 py-2 bg-green-700 text-white text-sm font-medium rounded-xl hover:bg-green-800 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download Member Import Template (CSV)
        </a>
      </div>

      {/* How to run on Render */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-800">Running Import Commands on Render</h2>

        <div className="space-y-1">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Step 1 — Open the Render Shell</h3>
          <p className="text-sm text-gray-600">
            Go to your <strong>Render dashboard</strong>, select the backend service, then click the <strong>Shell</strong> tab.
          </p>
        </div>

        <div className="space-y-1">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Step 2 — Import Members</h3>
          <p className="text-sm text-gray-600 mb-2">
            Run the following command to import members from the standard member CSV (Breeze export format):
          </p>
          <pre className="bg-gray-900 text-green-300 rounded-xl px-4 py-3 text-xs overflow-x-auto">
{`python manage.py import_members /path/to/members.csv`}
          </pre>
        </div>

        <div className="space-y-1">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Step 3 — Import Payments (Tithe.ly/Breeze)</h3>
          <p className="text-sm text-gray-600 mb-2">
            For Tithe.ly or Breeze payment exports, use the payment members import command:
          </p>
          <pre className="bg-gray-900 text-green-300 rounded-xl px-4 py-3 text-xs overflow-x-auto">
{`python manage.py import_payment_members /path/to/payments.csv`}
          </pre>
        </div>

        <div className="space-y-1">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Step 4 — Verify</h3>
          <p className="text-sm text-gray-600">
            After running the import, check the <strong>Members</strong> and <strong>Payments</strong> pages in this admin panel to verify the data was imported correctly.
          </p>
        </div>
      </div>

      {/* Tithe.ly / Breeze CSV columns reference */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-4">CSV Column Reference</h2>

        <div className="space-y-6">
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Member Import Template Columns
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-gray-100 rounded-xl overflow-hidden">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Column</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Required</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {[
                    { col: "first_name", req: "Yes", note: "Member first name" },
                    { col: "last_name", req: "Yes", note: "Member last name" },
                    { col: "email", req: "No", note: "Contact email address" },
                    { col: "phone", req: "No", note: "Primary phone number" },
                    { col: "join_date", req: "Yes", note: "YYYY-MM-DD format" },
                    { col: "status", req: "No", note: "active, inactive, suspended (default: active)" },
                    { col: "tier", req: "No", note: "standard, senior, family (default: standard)" },
                    { col: "notes", req: "No", note: "Internal notes" },
                  ].map((row) => (
                    <tr key={row.col} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs text-gray-700">{row.col}</td>
                      <td className="px-4 py-2 text-xs">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          row.req === "Yes" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-500"
                        }`}>
                          {row.req}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500">{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Tithe.ly / Breeze Export Columns (payment_members import)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-gray-100 rounded-xl overflow-hidden">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Column</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {[
                    { col: "First Name", note: "Member first name (used for matching)" },
                    { col: "Last Name", note: "Member last name (used for matching)" },
                    { col: "Amount", note: "Payment amount in dollars (e.g. 50.00)" },
                    { col: "Date", note: "Payment date (M/D/YYYY or YYYY-MM-DD)" },
                    { col: "Payment Method", note: "check, cash, bank_transfer, online, etc." },
                    { col: "Check / Transaction Number", note: "Reference number (optional)" },
                    { col: "Fund Name", note: "Ignored — all mapped to contributions" },
                    { col: "Note", note: "Optional notes" },
                  ].map((row) => (
                    <tr key={row.col} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs text-gray-700">{row.col}</td>
                      <td className="px-4 py-2 text-xs text-gray-500">{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Tips */}
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-amber-900 mb-2">Tips &amp; Common Issues</h2>
        <ul className="text-sm text-amber-800 space-y-1.5 list-disc list-inside">
          <li>Always back up the database before running a bulk import.</li>
          <li>Member matching uses fuzzy name matching — review the import log for unmatched rows.</li>
          <li>Dates must be in YYYY-MM-DD format for the member template; Tithe.ly exports use M/D/YYYY.</li>
          <li>Re-running the import with the same file is safe — duplicate detection prevents double entries.</li>
          <li>If a member cannot be matched, the payment is flagged for manual review in the Reconciliation queue.</li>
        </ul>
      </div>
    </div>
  );
}
