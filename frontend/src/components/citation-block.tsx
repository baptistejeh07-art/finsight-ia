"use client";

import { useEffect, useState } from "react";
import { QUOTES } from "@/data/quotes";

export function CitationBlock() {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setIdx(Math.floor(Math.random() * QUOTES.length));
  }, []);

  const q = QUOTES[idx];

  return (
    <div className="text-center">
      <div
        style={{
          fontSize: "13px",
          fontWeight: 300,
          fontStyle: "italic",
          lineHeight: "1.7",
          color: "#777",
          marginBottom: "8px",
        }}
      >
        « {q.text} »
      </div>
      <div
        style={{
          fontSize: "10px",
          fontWeight: 500,
          color: "#999",
          letterSpacing: "1px",
          textTransform: "uppercase",
        }}
      >
        {q.author}
      </div>
    </div>
  );
}
