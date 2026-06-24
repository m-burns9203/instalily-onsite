import { useState } from "react";
import { api } from "../lib/api";
import type { Outreach } from "../lib/types";

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable (e.g. non-secure context) — no-op */
        }
      }}
      className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-700"
    >
      {copied ? "✓ Copied" : label}
    </button>
  );
}

export function OutreachPanel({ leadId }: { leadId: number }) {
  const [data, setData] = useState<Outreach | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.outreach(leadId));
    } catch (e) {
      setError(`Couldn't generate outreach (${String(e)})`);
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <div className="mt-6 rounded-xl border border-dashed border-brand-300 bg-brand-50/40 p-5 text-center">
        <p className="text-sm text-slate-600">
          Generate a ready-to-send cold email and call opener, personalized from
          this lead's profile.
        </p>
        <button
          onClick={generate}
          disabled={loading}
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-60"
        >
          {loading ? "Drafting…" : "✉ Draft outreach"}
        </button>
        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
      </div>
    );
  }

  const fullEmail = `Subject: ${data.subject}\n\n${data.email_body}`;

  return (
    <div className="mt-6 rounded-xl border border-brand-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <span aria-hidden>✉</span> Suggested outreach
        </h2>
        <button onClick={generate} className="text-xs text-brand-600 hover:underline">
          ↻ Regenerate
        </button>
      </div>

      {/* Email */}
      <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Cold email
          </span>
          <CopyButton text={fullEmail} label="Copy email" />
        </div>
        <div className="text-sm font-semibold text-slate-800">{data.subject}</div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
          {data.email_body}
        </p>
      </div>

      {/* Call opener */}
      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Cold-call opener
            {data.contact.title && (
              <span className="ml-1 normal-case text-slate-400">
                · ask for the {data.contact.title}
              </span>
            )}
          </span>
          <CopyButton text={data.call_opener} label="Copy script" />
        </div>
        <p className="text-sm italic leading-relaxed text-slate-700">
          "{data.call_opener}"
        </p>
      </div>

      <p className="mt-3 text-xs text-slate-400">
        Draft generated from this lead's enrichment — review before sending.
      </p>
    </div>
  );
}
