"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { FolderPlus } from "lucide-react";
import {
  attachAnalysisToCase, createCase, getCases,
  type InvestigationCase,
} from "@/services/api";

export default function AnalysisActions({ analysisId, token }: { analysisId: string; token: string }) {
  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [selected, setSelected] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [createNew, setCreateNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    void getCases(token).then((items) => {
      if (!cancelled) setCases(items);
    }).catch(() => {
      if (!cancelled) setError("Could not load existing cases. Report download is available in Additional AI Explanations.");
    });
    return () => { cancelled = true; };
  }, [token]);

  async function attach(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!createNew && !selected) { setError("Select a case first."); return; }
    if (createNew && newTitle.trim().length < 3) { setError("Enter a case title (at least 3 characters)."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      let destination = selected;
      if (createNew) {
        const created = await createCase(token, newTitle.trim(), newDescription.trim());
        destination = created.id;
        setCases((previous) => [created, ...previous]);
        setSelected(created.id);
        setCreateNew(false);
        setNewTitle("");
        setNewDescription("");
      }
      // If attachment fails, the newly created case remains, so retrying won't duplicate it.
      await attachAnalysisToCase(token, destination, analysisId);
      setMessage("Analysis attached successfully. View it on the Cases page.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to attach the analysis.");
    } finally { setBusy(false); }
  }


  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-8 space-y-5">
      <h2 className="text-2xl font-bold">Investigation Case</h2>
      <p className="text-sm text-slate-400">Attach this saved analysis to an open investigation case. The PDF download is in Additional AI Explanations above.</p>
      <form onSubmit={(e) => void attach(e)} className="space-y-4 rounded-2xl border border-white/10 bg-black/20 p-5">
        <h3 className="flex gap-2 items-center font-semibold"><FolderPlus size={18}/> Add this analysis to an investigation case</h3>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={createNew} onChange={(e) => setCreateNew(e.target.checked)}/> Create a new case instead</label>
        {createNew ? (
          <>
            <input aria-label="New case title" minLength={3} maxLength={150} required value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="New case title" className="w-full rounded-lg bg-slate-900 border border-white/10 p-3"/>
            <textarea aria-label="New case description" maxLength={2000} rows={2} value={newDescription} onChange={(e) => setNewDescription(e.target.value)} placeholder="Case description (optional)" className="w-full rounded-lg bg-slate-900 border border-white/10 p-3"/>
          </>
        ) : (
          <select aria-label="Choose existing case" value={selected} onChange={(e) => setSelected(e.target.value)} required className="w-full rounded-lg bg-slate-900 border border-white/10 p-3">
            <option value="">Select an open case</option>
            {cases.filter((c) => c.status === "open").map((c) => <option value={c.id} key={c.id}>{c.title}</option>)}
          </select>
        )}
        <button type="submit" disabled={busy} className="rounded-xl bg-cyan-600 px-5 py-3 font-semibold disabled:opacity-50">{busy ? "Working..." : "Add to case"}</button>
        <Link href="/cases" className="ml-4 text-cyan-300 underline">Manage cases</Link>
      </form>
      {error && <p role="alert" className="text-red-300">{error}</p>}
      {message && <p role="status" className="text-emerald-300">{message}</p>}
    </section>
  );
}
