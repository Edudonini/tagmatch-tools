"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { NAV_ITEMS, isNavActive } from "./nav";
import { SessionBar } from "./SessionBar";
import { loadSession } from "./sessionStore";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";

  // Hydrate the tab session once so the chips can appear before any page reads it.
  useEffect(() => {
    void loadSession();
  }, []);

  return (
    <>
      <header className="app-topbar">
        <Link href="/" className="app-brand" aria-label="TagMatch Tools — início">
          <svg viewBox="0 0 40 40" fill="none" aria-hidden="true" className="app-brand-glyph">
            <path d="M7 5L35 20L7 35V26L19 20L7 14V5Z" fill="var(--accent)" />
            <rect x="3" y="18" width="7" height="4" rx="1" fill="var(--accent)" opacity="0.6" />
          </svg>
          <span className="app-brand-name">TAGMATCH TOOLS</span>
        </Link>
        <nav className="app-nav" aria-label="Ferramentas">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`app-nav-item${active ? " active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="app-topbar-right">
          <SessionBar />
        </div>
      </header>
      {children}
    </>
  );
}
