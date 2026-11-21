import { useCallback, useEffect, useRef, useState } from "react";
import { ConsoleView } from "../components/ConsoleView";
import { EntryView } from "../components/EntryView";
import { TimeoutError, TriageError, triage } from "../lib/api";
import type { RunState } from "../lib/run";
import type { Sample } from "../mocks";
import type { TriageRequest } from "../types/triage";

export function ConsolePage() {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [bodyError, setBodyError] = useState(false);
  const [run, setRun] = useState<RunState>({ kind: "idle" });
  const [resultBody, setResultBody] = useState<string | null>(null);
  const lastReq = useRef<TriageRequest | null>(null);
  const runId = useRef(0);
  const inflight = useRef<AbortController | null>(null);

  const start = useCallback(async (req: TriageRequest) => {
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;
    lastReq.current = req;
    const id = ++runId.current;
    const startedAt = Date.now();
    setRun({ kind: "loading", startedAt });
    try {
      const res = await triage(req, ctrl.signal);
      if (id !== runId.current) return;
      setResultBody(req.body);
      setRun({ kind: "success", res, runId: id });
    } catch (e) {
      if (id !== runId.current) return;
      // Cancelled by us (New ticket, unmount, hot reload): not a user-facing error.
      if (ctrl.signal.aborted) return;
      const elapsedMs = Date.now() - startedAt;
      if (e instanceof TimeoutError) setRun({ kind: "timeout", elapsedMs });
      else if (e instanceof TriageError) setRun({ kind: "error", code: e.code, message: e.message, elapsedMs });
      else setRun({ kind: "error", code: "CLIENT", message: e instanceof Error ? e.message : String(e), elapsedMs });
    }
  }, []);

  const submit = useCallback(() => {
    if (run.kind === "loading") return;
    if (!body.trim()) {
      setBodyError(true);
      document.getElementById("body")?.focus();
      return;
    }
    // D3: empty subject is fine and is sent as null.
    start({ subject: subject.trim() ? subject : null, body });
    // The entry view swaps to the two-pane layout; keep focus on the (re-mounted) Triage button.
    requestAnimationFrame(() => document.getElementById("triage-btn")?.focus());
  }, [body, subject, run.kind, start]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        submit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [submit]);

  useEffect(() => () => inflight.current?.abort(), []);

  const newTicket = () => {
    inflight.current?.abort();
    runId.current++; // drop any in-flight result
    setRun({ kind: "idle" });
    setSubject("");
    setBody("");
    setBodyError(false);
    setResultBody(null);
  };

  const fields = {
    subject,
    body,
    onSubject: setSubject,
    onBody: (v: string) => {
      setBody(v);
      if (v.trim()) setBodyError(false);
    },
    onSample: (s: Sample) => {
      setSubject(s.request.subject ?? "");
      setBody(s.request.body);
      setBodyError(false);
    },
    onSubmit: submit,
    bodyError,
  };

  // Entry-first: before the first submit (or after "New ticket") only the ticket entry is shown.
  if (run.kind === "idle") return <EntryView {...fields} />;

  return (
    <ConsoleView
      {...fields}
      onNew={newTicket}
      onRetry={() => {
        if (!lastReq.current) return;
        start(lastReq.current);
        document.getElementById("triage-btn")?.focus(); // review #7: Retry unmounts, keep focus somewhere useful
      }}
      run={run}
      resultBody={resultBody}
    />
  );
}
