
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/auth/AuthProvider";
import { authenticatedFetch } from "@/services/api";

type BackendHealth = {
  status: string;
  inference_ready: boolean;
  inference_reason: string | null;
  stage: string;
};

export default function SettingsPage() {
  const { user, token, logout } = useAuth();
  const router = useRouter();

  const [health, setHealth] = useState<BackendHealth | null>(
    null
  );
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;

    const authToken: string = token;
    let cancelled = false;

    async function checkBackend() {
      try {
        const response = await authenticatedFetch(
          "/api/health",
          authToken
        );

        if (!response.ok) {
          throw new Error("Backend health check failed.");
        }

        const data =
          (await response.json()) as BackendHealth;

        if (!cancelled) {
          setHealth(data);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setError("Unable to connect to the backend.");
        }
      } finally {
        if (!cancelled) {
          setChecking(false);
        }
      }
    }

    void checkBackend();

    return () => {
      cancelled = true;
    };
  }, [token]);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen px-8 pb-20 pt-32 text-white lg:ml-[340px]">
      <Sidebar />

      <h1 className="text-4xl font-bold md:text-5xl">
        Settings
      </h1>

      <p className="mt-4 text-slate-400">
        Investigator account and application configuration.
      </p>

      <div className="mt-10 max-w-4xl space-y-8">

        {/* Investigator Profile */}
        <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
          <h2 className="text-2xl font-bold">
            Investigator Profile
          </h2>

          <div className="mt-6 space-y-5">
            <Detail label="Full Name" value={user?.name ?? "N/A"} />
            <Detail label="Email Address" value={user?.email ?? "N/A"} />
            <Detail label="Account Role" value={user?.role ?? "N/A"} />
            <Detail label="Account ID" value={user?.id ?? "N/A"} />
          </div>

          <p className="mt-5 text-sm text-slate-400">
            Profile details are read-only in this version.
          </p>
        </section>

        {/* Model Configuration */}
        <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
          <h2 className="text-2xl font-bold">
            AI Model Configuration
          </h2>

          <div className="mt-6 space-y-5">
            <Detail label="Active Model" value="ResNet50V2" />
            <Detail label="Inference Mode" value="Single Model" />
            <Detail
              label="Explainability"
              value="Grad-CAM"
            />
            <Detail
              label="Backend Status"
              value={
                checking
                  ? "Checking..."
                  : error
                    ? "Unavailable"
                    : health?.status ?? "Unknown"
              }
            />
            <Detail
              label="Model Readiness"
              value={
                checking
                  ? "Checking..."
                  : health?.inference_ready
                    ? "Ready"
                    : "Not Ready"
              }
            />
          </div>

          <p className="mt-5 text-sm text-amber-200">
            Model configuration is managed by the backend.
            Ensemble inference will be added later.
          </p>
        </section>

        {/* Account Security */}
        <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
          <h2 className="text-2xl font-bold">
            Account Security
          </h2>

          <p className="mt-4 text-slate-400">
            Your current login session is temporary.
            Sign out when you finish working with
            investigation evidence.
          </p>

          <div className="mt-6">
            <Detail
              label="Authentication"
              value="JWT Bearer Token"
            />
            <Detail
              label="Session Persistence"
              value="In-memory (development)"
            />
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="mt-8 rounded-xl border border-red-400/30 bg-red-500/10 px-6 py-3 font-semibold text-red-300 hover:bg-red-500/20"
          >
            Sign Out
          </button>
        </section>

        {/* Application Information */}
        <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
          <h2 className="text-2xl font-bold">
            About NeuralEdge AI
          </h2>

          <p className="mt-4 text-slate-300">
            An Explainable Deep Learning Framework for
            Deepfake Image Detection to Support Cybercrime
            Investigations.
          </p>

          <p className="mt-4 text-sm text-slate-400">
            This platform provides AI-assisted forensic triage.
            Predictions and explanation heatmaps support human
            investigation and do not establish authenticity
            or manipulation as a matter of fact.
          </p>
        </section>

      </div>
    </div>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="border-b border-white/10 py-3">
      <p className="text-sm text-slate-400">
        {label}
      </p>

      <p className="mt-2 break-all font-medium">
        {value}
      </p>
    </div>
  );
}
