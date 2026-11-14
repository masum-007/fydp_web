"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { UserCircle, ChevronDown, Settings, LogOut } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";

/**
 * One seamless, edge-to-edge header for public and investigator pages.
 * The landing page still compacts on scroll; the investigator header stays
 * the same height to maintain stable alignment with the workspace sidebar.
 * Fixed positioning works inside the landing page's overflow-hidden wrapper.
 */
export default function Navbar() {
  const { user, status, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isLanding = pathname === "/";
  const [isScrolled, setIsScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!isLanding) {
      setIsScrolled(false);
      return;
    }

    // Refresh and back/forward navigation must also show the correct size.
    const update = () => setIsScrolled(window.scrollY > 48);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [isLanding]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", key);
    };
  }, []);

  async function signOut() {
    try {
      await logout();
      setOpen(false);
      router.replace("/login");
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Could not sign out.");
    }
  }

  const compact = isLanding && isScrolled;

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 border-b backdrop-blur-xl transition-[height,background-color,border-color,box-shadow] duration-300 ease-out motion-reduce:transition-none ${
        compact
          ? "h-[62px] border-cyan-400/20 bg-[#050816]/95 shadow-[0_8px_28px_rgba(0,0,0,0.18)]"
          : "h-[76px] border-white/10 bg-[#050816]/95"
      }`}
    >
      <div className="mx-auto flex h-full w-full max-w-[1920px] items-center justify-between gap-4 px-4 sm:px-8 lg:px-10">
        <Link
          href={user ? "/dashboard" : "/"}
          className="flex min-w-0 items-center gap-2 sm:gap-3 focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
          aria-label="NeuralEdge AI home"
        >
          <span
            className={`flex shrink-0 items-center justify-center overflow-hidden rounded-xl border border-cyan-400/30 bg-[#050816] transition-[width,height] duration-300 ease-out motion-reduce:transition-none ${
              compact ? "h-9 w-9" : "h-9 w-9 sm:h-11 sm:w-11"
            }`}
          >
            <Image
              src="/branding/neuraledge-mark.png"
              alt=""
              width={160}
              height={160}
              priority
              className="h-full w-full object-cover"
              aria-hidden="true"
            />
          </span>
          <span className="min-w-0">
            <span className={`block whitespace-nowrap font-bold text-white transition-[font-size] duration-300 motion-reduce:transition-none ${compact ? "text-base" : "text-base sm:text-lg"}`}>
              NeuralEdge AI
            </span>
            <span
              className={`hidden overflow-hidden whitespace-nowrap text-xs sm:block leading-4 text-slate-400 transition-[max-height,opacity] duration-300 ease-out motion-reduce:transition-none ${
                compact ? "max-h-0 opacity-0" : "max-h-5 opacity-100"
              }`}
            >
              AI Forensic Intelligence
            </span>
          </span>
        </Link>

        {user ? (
          <div ref={menuRef} className="relative shrink-0">
            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              aria-haspopup="menu"
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-left hover:border-cyan-400/40 sm:gap-3 sm:px-4"
            >
              <UserCircle size={24} className="text-cyan-400" aria-hidden="true" />
              <span className="max-w-[150px] truncate text-sm font-semibold text-white">{user.name}</span>
              <ChevronDown size={17} className="text-slate-400" aria-hidden="true" />
            </button>
            {open && (
              <div role="menu" aria-label="Account menu" className="absolute right-0 mt-2 w-64 rounded-xl border border-white/15 bg-[#111a2b] p-2 shadow-2xl">
                <div className="border-b border-white/10 px-3 py-3">
                  <p className="truncate text-sm font-semibold text-white">{user.name}</p>
                  <p className="truncate text-xs text-slate-400">{user.email}</p>
                </div>
                <Link role="menuitem" href="/settings#profile" className="mt-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-white/10">
                  <UserCircle size={17} aria-hidden="true" /> My profile
                </Link>
                <Link role="menuitem" href="/settings" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-white/10">
                  <Settings size={17} aria-hidden="true" /> Settings &amp; security
                </Link>
                <button role="menuitem" type="button" onClick={() => void signOut()} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-red-300 hover:bg-red-400/10">
                  <LogOut size={17} aria-hidden="true" /> Logout
                </button>
              </div>
            )}
          </div>
        ) : (
          <nav aria-label="Public navigation" className="flex shrink-0 items-center gap-2 text-sm sm:gap-3">
            {status === "checking" ? (
              <span className="text-xs text-slate-400 sm:text-sm">Checking session...</span>
            ) : (
              <>
                <Link href="/" className="hidden text-slate-300 hover:text-white sm:block">Home</Link>
                <Link href="/detect" className="hidden text-cyan-300 hover:text-white sm:inline">Try detection</Link>
                <Link href="/login" className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-cyan-200 transition-colors hover:bg-cyan-400/20">Login</Link>
              </>
            )}
          </nav>
        )}
      </div>
    </header>
  );
}
