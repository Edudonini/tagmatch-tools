export type Stat = {
  label: string;
  value: string;
  tone?: "default" | "accent";
  accessory?: React.ReactNode;
};

export function StatRail({ stats }: { stats: Stat[] }) {
  if (stats.length === 0) return null;
  return (
    <div className="stat-rail">
      {stats.map((s) => (
        <div className="stat-rail-item" key={s.label}>
          <div className="stat-rail-label">{s.label}</div>
          <div className={`stat-rail-value${s.tone === "accent" ? " accent" : ""}`}>{s.value}</div>
          {s.accessory}
        </div>
      ))}
    </div>
  );
}
