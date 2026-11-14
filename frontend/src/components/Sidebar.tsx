"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, X, LayoutDashboard, ScanFace, FolderOpen, FileText, BrainCircuit, Settings } from "lucide-react";

const items = [
  { label: "Dashboard", path: "/dashboard", Icon: LayoutDashboard },
  { label: "Analyze Image", path: "/analyze", Icon: ScanFace },
  { label: "Investigation Cases", path: "/cases", Icon: FolderOpen },
  { label: "Reports", path: "/reports", Icon: FileText },
  { label: "Model Analytics", path: "/model-analytics", Icon: BrainCircuit },
  { label: "Settings", path: "/settings", Icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [pathname]);
  return <>
    <button type="button" onClick={() => setOpen(true)} aria-label="Open navigation" aria-expanded={open}
      className="fixed left-5 top-28 z-40 rounded-xl border border-cyan-400/30 bg-[#111b2c] p-3 text-cyan-300 shadow-lg lg:hidden">
      <Menu size={23} />
    </button>
    {open && <button type="button" aria-label="Close navigation overlay" onClick={() => setOpen(false)} className="fixed inset-0 z-40 bg-black/70 lg:hidden" />}
    <aside aria-label="Investigation navigation" className={`fixed bottom-5 left-5 top-28 z-50 w-[270px] overflow-y-auto rounded-3xl border border-cyan-400/15 bg-[#0a1020]/95 p-5 shadow-xl backdrop-blur-xl transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-[120%]"}`}>
      <div className="mb-7 flex items-center justify-between px-2 pt-1">
        <h2 className="text-base font-bold text-cyan-300">Investigation Panel</h2>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close navigation" className="rounded-lg p-2 text-slate-400 hover:bg-white/10 lg:hidden"><X size={20}/></button>
      </div>
      <nav className="space-y-2">{items.map(({label,path,Icon}) => {
        const active = pathname === path || pathname.startsWith(path + "/");
        return <Link key={path} href={path} aria-current={active ? "page" : undefined} onClick={() => setOpen(false)}
          className={`flex min-h-12 items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${active ? "border border-cyan-400/20 bg-cyan-400/10 text-cyan-300" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}>
          <Icon size={19} aria-hidden="true"/><span>{label}</span>
        </Link>;
      })}</nav>
      <p className="mt-10 border-t border-white/10 px-2 pt-5 text-xs leading-5 text-slate-500">NeuralEdge AI · Investigator workspace</p>
    </aside>
  </>;
}
