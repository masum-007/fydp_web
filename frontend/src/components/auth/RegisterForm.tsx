
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { registerInvestigator } from "@/services/api";

export default function RegisterForm() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleRegister(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");

    if (password.length < 12) {
      setError("Password must contain at least 12 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await registerInvestigator(
        name.trim(),
        email.trim(),
        password
      );

      // Registration creates the account.
      // The user must then log in separately.
      router.push("/login");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Registration failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-8 text-white">
      <h1 className="text-3xl font-bold">
        Create Investigator Account
      </h1>

      <p className="mt-3 text-slate-400">
        Register for the NeuralEdge AI investigation workspace.
      </p>

      <form onSubmit={handleRegister} className="mt-8 space-y-4">
        <div>
          <label htmlFor="name" className="mb-2 block text-sm">
            Full Name
          </label>
          <input
            id="name"
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/20 p-3"
            placeholder="Your full name"
          />
        </div>

        <div>
          <label htmlFor="email" className="mb-2 block text-sm">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/20 p-3"
            placeholder="investigator@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-2 block text-sm">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/20 p-3"
            placeholder="At least 12 characters"
          />
        </div>

        <div>
          <label htmlFor="confirm" className="mb-2 block text-sm">
            Confirm Password
          </label>
          <input
            id="confirm"
            type="password"
            required
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-black/20 p-3"
            placeholder="Repeat password"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-cyan-600 py-3 font-semibold disabled:opacity-50"
        >
          {loading ? "Creating Account..." : "Create Account"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-400">
        Already have an account?{" "}
        <Link href="/login" className="text-cyan-400 hover:underline">
          Login
        </Link>
      </p>
    </div>
  );
}
