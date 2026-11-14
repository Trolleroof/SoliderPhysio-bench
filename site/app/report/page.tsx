"use client";

import { useEffect } from "react";

export default function ReportRedirect() {
  useEffect(() => {
    window.location.replace("/#methodology");
  }, []);

  return (
    <div className="wrap" style={{ padding: "64px 24px" }}>
      <p>
        Redirecting to the combined post… <a className="arrow-link" href="/#methodology">Jump to Methodology</a>
      </p>
    </div>
  );
}
