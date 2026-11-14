"use client";

import { useEffect, useState } from "react";
import { Image as ImageIcon } from "lucide-react";
import { getEvidenceThumbnail } from "@/services/api";

export default function EvidenceThumbnail({ evidenceId, token, size = "regular" }: {
  evidenceId: string; token: string; size?: "compact" | "regular";
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    void getEvidenceThumbnail(evidenceId, token).then((value) => {
      objectUrl = value;
      if (!cancelled) { setUrl(value); setError(false); }
      else URL.revokeObjectURL(value);
    }).catch(() => { if (!cancelled) setError(true); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [evidenceId, token]);

  return (
    <div className={`flex shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-slate-900 ${size === "compact" ? "h-12 w-12" : "h-24 w-24"}`} aria-label="Evidence preview">
      {url ? (
        // Object URL from an authenticated JPEG endpoint, never a public image link.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="Preview of submitted evidence" className="h-full w-full object-cover" />
      ) : (
        <div className="flex flex-col items-center gap-1 text-center text-xs text-slate-500">
          <ImageIcon size={22} aria-hidden="true" />
          {size === "compact" ? "" : error ? "Preview unavailable" : "Loading preview"}
        </div>
      )}
    </div>
  );
}
