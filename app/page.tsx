import Link from "next/link";

export default function Home() {
  return (
    <main style={{ padding: 24, fontFamily: "sans-serif" }}>
      <h1>TagMatch Tools</h1>
      <ul>
        <li>
          <Link href="/extract-map">Map Extraction</Link>
        </li>
      </ul>
    </main>
  );
}
