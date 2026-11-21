import { useEffect, useState } from "react";

let push: ((msg: string) => void) | null = null;
export const toast = (msg: string) => push?.(msg);

export function ToastHost() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    push = (m) => {
      setMsg(m);
      clearTimeout(t);
      t = setTimeout(() => setMsg(null), 1800);
    };
    return () => {
      push = null;
      clearTimeout(t);
    };
  }, []);
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center">
      {msg && (
        <div className="rounded-md border border-line-strong bg-ink px-3 py-2 text-[13px] text-bg shadow-lg">{msg}</div>
      )}
    </div>
  );
}
