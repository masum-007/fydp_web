
"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export default function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    setLoading(true);
    setError("");

    try {
      await login(email, password);

      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to log in. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-10 backdrop-blur-xl">

      <h1 className="text-3xl font-bold text-white">
        Investigator Login
      </h1>

      <p className="mt-3 text-slate-400">
        Access NeuralEdge AI forensic workspace
      </p>

      <form onSubmit={handleLogin}>

        <input
          type="email"
          placeholder="Email"
          aria-label="Email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-8 w-full rounded-xl border border-white/10 bg-black/20 p-4 text-white"
        />

        <input
          type="password"
          placeholder="Password"
          aria-label="Password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-4 w-full rounded-xl border border-white/10 bg-black/20 p-4 text-white"
        />

        {error && (
          <p role="alert" className="mt-4 text-sm text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-8 w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 py-4 font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Logging in..." : "Login"}
        </button>

      </form>
      <p className="mt-6 text-center text-sm text-slate-400">
Don&apos;t have an investigator account?{" "}
  <Link href="/register" className="text-cyan-400 hover:underline">
    Register here
  </Link>
</p>
    </div>
  );
}
