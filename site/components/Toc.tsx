"use client";

import { useEffect, useState } from "react";

const ITEMS = [
  { id: "intro", label: "Introduction" },
  { id: "leaderboard", label: "Results" },
  { id: "cost", label: "Cost" },
  { id: "findings", label: "Key findings" },
  { id: "methodology", label: "Methodology" },
  { id: "tasks", label: "Tasks" },
  { id: "scoring", label: "Scoring" },
  { id: "limits", label: "Limits" },
];

// Vertical contents rail with scroll-spy: sections already passed fade out,
// the current one is bold, upcoming ones sit at a middle opacity.
export function Toc() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const line = window.innerHeight * 0.35;
      let idx = 0;
      ITEMS.forEach((item, i) => {
        const el = document.getElementById(item.id);
        if (el && el.getBoundingClientRect().top <= line) idx = i;
      });
      // at the very bottom, the last section counts as current even if short
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) idx = ITEMS.length - 1;
      setActive(idx);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <nav className="toc" aria-label="Contents">
      <div className="toc-title">Contents</div>
      <ol style={{ "--p": active / (ITEMS.length - 1) } as React.CSSProperties}>
        {ITEMS.map((item, i) => (
          <li key={item.id} className={i < active ? "past" : i === active ? "current" : "next"}>
            <a href={`#${item.id}`} aria-current={i === active ? "location" : undefined}>
              {item.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
