"use client";

export function Header() {
  return (
    <header className="site-header">
      <div className="wrap">
        <a href="/" className="brand">
          soldierphysio
        </a>
        <nav className="nav" aria-label="Main">
          <a href="/#methodology">Methodology</a>
          <a href="/#leaderboard">Results</a>
          <a href="/#findings">Key takeaways</a>
          <a href="/traces/">Traces</a>
        </nav>
      </div>
    </header>
  );
}
