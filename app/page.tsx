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
    href: "#",
    glyph: "QB",
    name: "Query Builder",
    desc: "Generate matching queries from a spec — coming soon.",
    available: false,
  },
  {
    href: "#",
    glyph: "LX",
    name: "Log Extraction",
    desc: "Pull raw analytics logs for a run — coming soon.",
    available: false,
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
