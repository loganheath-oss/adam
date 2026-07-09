"use client";

import { useEffect, useState } from "react";

// Copyable sprint link for handing the sprint to the creative team.
export function CopyLink({ path }: { path: string }) {
  const [url, setUrl] = useState(path);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setUrl(window.location.origin + path);
  }, [path]);

  const copy = () => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="mt-2.5 flex items-center gap-2">
      <input
        readOnly
        value={url}
        onFocus={(e) => e.currentTarget.select()}
        className="flex-1 rounded-md border border-blue-200 bg-white px-2.5 py-2 font-mono text-xs text-slate-600 outline-none"
      />
      <button
        type="button"
        onClick={copy}
        className={`rounded-md border px-3.5 py-2 text-xs font-medium transition ${copied ? "border-green-300 bg-green-50 text-green-700" : "border-slate-300 bg-white hover:bg-slate-50"}`}
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}
