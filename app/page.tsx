import Link from "next/link";

const TOOLS = [
  {
    href: "/extract-map",
    glyph: "EX",
    name: "Map Extraction",
    desc: "Parse a Whimsical SVG export into a structured TagMatch event spec.",
    available: true,
  },
  {
    href: "/build-query",
    glyph: "QB",
    name: "Query Builder",
    desc: "Generate Databricks SQL (validation, volumetry, funnel, custom) from a spec.",
    available: true,
  },
  {
    href: "/match",
    glyph: "MT",
    name: "Matching",
    desc: "Compare an extracted spec against extracted logs — coverage, confidence, divergences.",
    available: true,
  },
  {
    href: "/extract-logs",
    glyph: "LX",
    name: "Log Extraction",
    desc: "Parse and merge Logcat/NDJSON/Dev JSON/Firebase logs into one events table.",
    available: true,
  },
  {
    href: "/convert-5.0",
    glyph: "5.0",
    name: "Converter para 5.0",
    desc: "Convert an extracted App 4 map to the App 5.0 taxonomy, with journey-context assist.",
    available: true,
  },
];

export default function Home() {
  return (
    <main className="shell">
      <div className="eyebrow">tagmatch / tools</div>
      <h1>TagMatch Tools</h1>
      <p className="lede">
        Standalone utilities for TagMatch spec extraction and QA — no login,
        no run history. Upload, process, download.
      </p>

      <div className="tool-list">
        {TOOLS.map((tool) => (
          <Link
            key={tool.name}
            href={tool.href}
            className={`panel tool-row${tool.available ? "" : " disabled"}`}
            aria-disabled={!tool.available}
          >
            <span className="glyph">{tool.glyph}</span>
            <span className="body">
              <span className="name">{tool.name}</span>
              <span className="desc">{tool.desc}</span>
            </span>
            <span className="arrow">{tool.available ? "→" : "·"}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
