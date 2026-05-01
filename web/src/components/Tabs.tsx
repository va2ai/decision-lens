import { useEffect, useState } from "react";

export interface TabDef {
  id: string;
  label: string;
  count?: number;
}

/**
 * Scroll-spy tab bar: clicking scrolls to the section, scrolling updates the active tab.
 *
 * Sections must have id={tab.id} and live in the same scroll container.
 * Following CAVC case-view pattern: scroll-spy only, never panel-switch.
 */
export function Tabs({ tabs }: { tabs: TabDef[] }) {
  const [active, setActive] = useState(tabs[0]?.id ?? "");

  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    const visible = new Set<string>();

    for (const tab of tabs) {
      const el = document.getElementById(tab.id);
      if (!el) continue;
      const obs = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) visible.add(tab.id);
          else visible.delete(tab.id);
          // First (topmost) currently-visible section wins.
          for (const t of tabs) {
            if (visible.has(t.id)) {
              setActive(t.id);
              return;
            }
          }
        },
        { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
      );
      obs.observe(el);
      observers.push(obs);
    }
    return () => observers.forEach((o) => o.disconnect());
  }, [tabs]);

  return (
    <nav className="sticky top-0 z-10 -mx-4 border-b border-zinc-200 bg-white/80 px-4 backdrop-blur">
      <ul className="flex gap-1 overflow-x-auto py-2">
        {tabs.map((t) => {
          const isActive = t.id === active;
          return (
            <li key={t.id}>
              <a
                href={`#${t.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(t.id)?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
                }}
                className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition ${
                  isActive
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-600 hover:bg-zinc-100"
                }`}
              >
                <span>{t.label}</span>
                {typeof t.count === "number" && (
                  <span
                    className={`rounded-full px-1.5 text-xs ${
                      isActive ? "bg-white/20" : "bg-zinc-200 text-zinc-700"
                    }`}
                  >
                    {t.count}
                  </span>
                )}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
