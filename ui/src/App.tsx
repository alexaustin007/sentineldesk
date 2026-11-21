import { useEffect, useState } from "react";
import { IconMoon, IconSun } from "./components/Icons";
import { ToastHost } from "./components/Toast";
import { USE_MOCK } from "./lib/api";
import { ConsolePage } from "./pages/ConsolePage";
import { DevStates } from "./pages/DevStates";
import { MetricsPage } from "./pages/MetricsPage";

type Route = "/" | "/metrics" | "/dev/states";

function currentRoute(): Route {
  const p = window.location.pathname.replace(/\/+$/, "") || "/";
  return p === "/metrics" || p === "/dev/states" ? p : "/";
}

function useRoute(): [Route, (r: Route) => void] {
  const [route, setRoute] = useState<Route>(currentRoute);
  useEffect(() => {
    const on = () => setRoute(currentRoute());
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  return [
    route,
    (r) => {
      window.history.pushState(null, "", r + window.location.search);
      setRoute(r);
    },
  ];
}

function useTheme(): [boolean, () => void] {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => {
      let stored: string | null = null;
      try {
        stored = localStorage.getItem("sd-theme");
      } catch {}
      if (!stored) setDark(mq.matches);
    };
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  return [
    dark,
    () =>
      setDark((d) => {
        try {
          localStorage.setItem("sd-theme", d ? "light" : "dark");
        } catch {}
        return !d;
      }),
  ];
}

const TABS: { route: Route; label: string }[] = [
  { route: "/", label: "Console" },
  { route: "/metrics", label: "Metrics" },
];

export function App() {
  const [route, go] = useRoute();
  const [dark, toggleTheme] = useTheme();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 h-12 border-b border-line bg-surface">
        <div className="flex h-full items-center gap-1 px-2 sm:gap-8 sm:px-6">
          <a
            href="/"
            onClick={(e) => {
              e.preventDefault();
              go("/");
            }}
            className="flex items-center gap-1 text-[14px] sm:gap-2.5 sm:text-[16px] font-semibold text-ink"
          >
            <svg aria-hidden viewBox="0 0 20 20" width="20" height="20" className="text-ink">
              <rect x="1" y="1" width="18" height="18" rx="4" fill="currentColor" />
              <path d="M6 10.5l2.5 2.5L14 7.5" fill="none" stroke="var(--surface)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            SentinelDesk
          </a>
          <nav aria-label="Sections" className="flex h-full items-stretch">
            {TABS.map((t) => (
              <a
                key={t.route}
                href={t.route}
                aria-current={route === t.route ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  go(t.route);
                }}
                className={`-mb-px flex items-center border-b-2 px-1.5 text-[14px] sm:px-3.5 sm:text-[15px] font-medium ${
                  route === t.route ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink"
                }`}
              >
                {t.label}
              </a>
            ))}
            {route === "/dev/states" && (
              <span aria-current="page" className="mono -mb-px flex items-center border-b-2 border-accent px-3 text-[13px] text-ink">
                /dev/states
              </span>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-1 sm:gap-3">
            <span
              className="flex h-7 items-center gap-1.5 rounded-full bg-surface-2 px-1.5 text-[12px] whitespace-nowrap sm:px-3 sm:text-[13px] text-ink-2"
              title={USE_MOCK ? "VITE_USE_MOCK=true" : "POST /api/triage"}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${USE_MOCK ? "bg-ink-4" : "bg-tone-low"}`} />
              {USE_MOCK ? "mock data" : "live API"}
            </span>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
              className="grid h-8 w-8 place-items-center rounded-md text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              {dark ? <IconSun /> : <IconMoon />}
            </button>
          </div>
        </div>
      </header>
      {route === "/" && <ConsolePage />}
      {route === "/metrics" && (
        <div className="px-6 py-6">
          <MetricsPage />
        </div>
      )}
      {route === "/dev/states" && (
        <div className="px-6 py-5">
          <DevStates />
        </div>
      )}
      <ToastHost />
    </div>
  );
}
