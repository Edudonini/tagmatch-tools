export type NavItem = { href: string; label: string };

export const NAV_ITEMS: NavItem[] = [
  { href: "/extract-map", label: "Mapa" },
  { href: "/extract-logs", label: "Logs" },
  { href: "/build-query", label: "Query" },
  { href: "/match", label: "Matching" },
  { href: "/convert-5.0", label: "5.0" },
  { href: "/validate-5.0", label: "Validar 5.0" },
];

export function isNavActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
