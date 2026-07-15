export type NextStep = {
  href: string;
  label: string;
  hint?: string;
  hintHref?: string;
};

export function nextStepsFor(
  tool: "extract-map" | "extract-logs",
  hasMap: boolean,
  hasLogs: boolean
): NextStep[] {
  if (tool === "extract-map") {
    return [
      { href: "/build-query", label: "Query Builder" },
      {
        href: "/match",
        label: "Matching",
        ...(hasLogs ? {} : { hint: "precisa de logs — extrair agora", hintHref: "/extract-logs" }),
      },
      { href: "/convert-5.0", label: "Converter para 5.0" },
    ];
  }
  // extract-logs
  return [
    {
      href: "/match",
      label: "Matching",
      ...(hasMap ? {} : { hint: "precisa de um mapa — extrair agora", hintHref: "/extract-map" }),
    },
  ];
}
