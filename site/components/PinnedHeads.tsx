"use client";

import { useEffect } from "react";

// Section titles are position: sticky in CSS, so they pin under the header while
// you read their section. This fades each one out over the last FADE px of its
// section, so it leaves slowly instead of being shoved off-screen.
const SELECTOR = ".block > h2, .block > .block-head, .writeup-sec > h3";
const FADE = 160;

export function PinnedHeads() {
  useEffect(() => {
    const heads = Array.from(document.querySelectorAll<HTMLElement>(SELECTOR));
    let frame = 0;
    const update = () => {
      frame = 0;
      for (const el of heads) {
        const box = el.parentElement?.getBoundingClientRect();
        if (!box) continue;
        const top = parseFloat(getComputedStyle(el).top) || 0;
        // room left between the bottom of the pinned title and the end of its section
        const room = box.bottom - (top + el.offsetHeight);
        el.style.opacity = String(Math.max(0, Math.min(1, room / FADE)));
      }
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
      heads.forEach((el) => (el.style.opacity = ""));
    };
  }, []);
  return null;
}
