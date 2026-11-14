"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "guest") {
      const destination = pathname?.startsWith("/") && !pathname.startsWith("//")
        ? pathname : "/dashboard";
      router.replace(`/login?next=${encodeURIComponent(destination)}`);
    }
  }, [status, pathname, router]);

  if (status === "checking") {
    return <div role="status" className="flex min-h-screen items-center justify-center text-slate-300">Restoring your secure session...</div>;
  }
  if (status !== "authenticated" || user?.role !== "investigator") {
    return <div role="status" className="flex min-h-screen items-center justify-center text-slate-300">Redirecting to investigator login...</div>;
  }
  return children;
}
