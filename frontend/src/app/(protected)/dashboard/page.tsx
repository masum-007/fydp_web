
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  FileSearch,
  ShieldAlert,
  CheckCircle,
  FileText,
  RefreshCw,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";
import StatsCard from "@/components/StatsCard";
import QuickActions from "@/components/QuickActions";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  getAnalysisHistory,
  type AnalysisResponse,
} from "@/services/api";

export default function Dashboard() {
  const { user, token } = useAuth();

  const [analyses, setAnalyses] =
    useState<AnalysisResponse[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshCount, setRefreshCount] = useState(0);

  useEffect(() => {
    if (!token) return;

    const authToken: string = token;
    let cancelled = false;

    async function fetchDashboard() {
      try {
        const data = await getAnalysisHistory(
          authToken,
          50,
          0
        );

        if (!cancelled) {
          setAnalyses(data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load dashboard."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchDashboard();

    return () => {
      cancelled = true;
    };
  }, [token, refreshCount]);

  const fakeCount = analyses.filter(
    (item) => item.prediction === "Fake"
  ).length;

  const realCount = analyses.filter(
    (item) => item.prediction === "Real"
  ).length;

  const recent = analyses.slice(0, 5);

  return (
    <div className="min-h-screen pt-32 text-white">
      <Sidebar />

      <main className="mx-auto max-w-[1600px] px-8 pb-20 pt-6 lg:ml-[340px]">

        {/* Dashboard Header */}
        <div className="flex flex-wrap items-start justify-between gap-6">

          <div>
            <h1 className="text-4xl font-bold md:text-5xl">
              Welcome back,
              <span className="text-cyan-400">
                {" "}{user?.name ?? "Investigator"}
              </span>
            </h1>

            <p className="mt-4 text-lg text-slate-400">
              Your AI-powered forensic investigation workspace.
            </p>
          </div>

          <button
            onClick={() => {
              setLoading(true);
              setRefreshCount((count) => count + 1);
            }}
            disabled={loading || !token}
            className="flex items-center gap-2 rounded-xl bg-cyan-600 px-5 py-3 font-semibold text-white disabled:opacity-50"
          >
            <RefreshCw size={18} />
            Refresh
          </button>
        </div>

        <div className="mt-6 inline-flex items-center gap-3 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-5 py-2 text-cyan-300">
          <span className="h-3 w-3 rounded-full bg-cyan-400" />
          Connected to your investigation records
        </div>

        <p className="mt-4 text-sm text-slate-400">
          Statistics are calculated from your latest
          50 analyses, not your entire database.
        </p>

        {/* Loading and Error Messages */}
        {loading && (
          <p role="status" className="mt-8 text-cyan-400">
            Loading real investigation statistics...
          </p>
        )}

        {error && (
          <div
            role="alert"
            className="mt-8 rounded-xl border border-red-400/30 bg-red-400/10 p-5 text-red-300"
          >
            {error}
          </div>
        )}

        {!token && (
          <p className="mt-8 text-amber-300">
            Please log in to access your dashboard.
          </p>
        )}

        {/* Real Statistics */}
        {!loading && !error && token && (
          <>
            <div className="mt-12 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">

              <StatsCard
                title="Loaded Analyses"
                value={String(analyses.length)}
                icon={<FileSearch />}
              />

              <StatsCard
                title="Classified Fake"
                value={String(fakeCount)}
                icon={<ShieldAlert />}
              />

              <StatsCard
                title="Classified Real"
                value={String(realCount)}
                icon={<CheckCircle />}
              />

              <StatsCard
                title="Generated Reports"
                value="Not available"
                icon={<FileText />}
              />

            </div>

            {/* Recent Analyses */}
            <section className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-8">

              <div className="flex flex-wrap items-center justify-between gap-4">

                <h2 className="text-2xl font-bold">
                  Recent Investigations
                </h2>

                <Link
                  href="/cases"
                  className="text-cyan-400 hover:underline"
                >
                  View All
                </Link>

              </div>

              {recent.length === 0 ? (
                <div className="mt-8">
                  <p className="text-slate-400">
                    No analyses have been saved yet.
                  </p>

                  <Link
                    href="/analyze"
                    className="mt-4 inline-block text-cyan-400 hover:underline"
                  >
                    Analyze your first image
                  </Link>
                </div>
              ) : (
                <div className="mt-6 overflow-x-auto">

                  <table className="w-full text-left">

                    <thead>
                      <tr className="border-b border-white/10 text-sm text-slate-400">
                        <th className="p-4">Analysis ID</th>
                        <th className="p-4">Prediction</th>
                        <th className="p-4">Confidence</th>
                        <th className="p-4">Model</th>
                        <th className="p-4">Date</th>
                      </tr>
                    </thead>

                    <tbody>
                      {recent.map((item) => (
                        <tr
                          key={item.analysis_id}
                          className="border-b border-white/5"
                        >
                          <td className="p-4 font-mono text-xs">
                            {item.analysis_id.slice(0, 8)}...
                          </td>

                          <td
                            className={`p-4 font-semibold ${
                              item.prediction === "Fake"
                                ? "text-red-400"
                                : "text-emerald-400"
                            }`}
                          >
                            {item.prediction}
                          </td>

                          <td className="p-4">
                            {(item.confidence * 100).toFixed(2)}%
                          </td>

                          <td className="p-4">
                            {item.model}
                          </td>

                          <td className="p-4 text-sm text-slate-400">
                            {new Date(
                              item.created_at
                            ).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>

                  </table>
                </div>
              )}

            </section>

            {/* Shortcuts */}
            <div className="mt-10">
              <QuickActions />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
