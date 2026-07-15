import Link from "next/link";

const TOOLS = [
  {
    href: "/extract-map",
    glyph: "MA",
    name: "Extração de Mapa",
    desc: "Transforma um export SVG do Whimsical num spec de eventos estruturado.",
    available: true,
  },
  {
    href: "/extract-logs",
    glyph: "LG",
    name: "Extração de Logs",
    desc: "Interpreta e mescla logs (Logcat, NDJSON, Dev JSON, Firebase) numa tabela única de eventos.",
    available: true,
  },
  {
    href: "/build-query",
    glyph: "QB",
    name: "Query Builder",
    desc: "Gera SQL do Databricks (validation, volumetry, funnel, custom) a partir de um spec.",
    available: true,
  },
  {
    href: "/match",
    glyph: "MT",
    name: "Matching",
    desc: "Compara um spec extraído com os logs — coverage, confiança e divergências.",
    available: true,
  },
  {
    href: "/convert-5.0",
    glyph: "5.0",
    name: "Converter para 5.0",
    desc: "Converte um mapa App 4 para a taxonomia App 5.0, com apoio de contexto de jornada.",
    available: true,
  },
];

export default function Home() {
  return (
    <main className="shell">
      <div className="eyebrow">tagmatch / tools</div>
      <h1>TagMatch Tools</h1>
      <p className="lede">
        Utilitários standalone para extração e QA de specs — sem login, sem
        histórico. Suba o arquivo, processe, baixe o resultado.
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
