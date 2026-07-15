import type { ConvEvent, Screen } from "./taxonomy5";

export type IndexedEvent = { ev: ConvEvent; index: number };
export type SnGroup = {
  sn: string;
  screens: Screen[];
  events: IndexedEvent[];
  hasScreenView: boolean;
};

// Groups events by their 4.0 sn (the screenName key that ties events to a
// screen), in order of first appearance. Events keep their global index so
// the page can update them in the flat state array.
export function groupBySn(events: ConvEvent[]): {
  withScreenView: SnGroup[];
  without: SnGroup[];
} {
  const order: string[] = [];
  const map = new Map<string, SnGroup>();
  events.forEach((ev, index) => {
    const sn = (ev.source_sn ?? "").trim();
    if (!map.has(sn)) {
      map.set(sn, { sn, screens: [], events: [], hasScreenView: false });
      order.push(sn);
    }
    const group = map.get(sn)!;
    group.events.push({ ev, index });
    if (ev.event_kind === "screen_view") {
      group.hasScreenView = true;
      if (Array.isArray(ev.screens)) group.screens.push(...ev.screens);
    }
  });
  const groups = order.map((sn) => map.get(sn)!);
  return {
    withScreenView: groups.filter((g) => g.hasScreenView),
    without: groups.filter((g) => !g.hasScreenView),
  };
}
