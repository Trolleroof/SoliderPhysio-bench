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
    // Fade only the text, never the box: the solid background must keep covering
    // whatever scrolls underneath, or the content shows through the title.
    const base = new Map(heads.map((el) => [el, getComputedStyle(el).color.match(/[\d.]+/g)?.slice(0, 3).join(", ")]));
    const setFade = (el: HTMLElement, o: number) => {
      const kids = Array.from(el.children) as HTMLElement[];
      if (kids.length) kids.forEach((k) => (k.style.opacity = o === 1 ? "" : String(o)));
      else el.style.color = o === 1 ? "" : `rgba(${base.get(el)}, ${o})`;
      el.style.pointerEvents = o < 0.2 ? "none" : "";
    };
    let frame = 0;
    // subsection titles pin directly under the pinned section title: measure it
    const measure = () => {
      const header = document.querySelector<HTMLElement>(".site-header");
      const h2 = document.querySelector<HTMLElement>("#methodology > h2");
      if (header && h2) document.documentElement.style.setProperty("--pin-sub", `${header.offsetHeight + h2.offsetHeight}px`);
    };
    measure();
    const update = () => {
      frame = 0;
      for (const el of heads) {
        const box = el.parentElement?.getBoundingClientRect();
        if (!box) continue;
        const top = parseFloat(getComputedStyle(el).top) || 0;
        // room left between the bottom of the pinned title and the end of its section
        const room = box.bottom - (top + el.offsetHeight);
        setFade(el, Math.max(0, Math.min(1, room / FADE)));
      }
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    const onResize = () => { measure(); onScroll(); };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (frame) cancelAnimationFrame(frame);
      heads.forEach((el) => setFade(el, 1));
    };
  }, []);
  return null;
}
