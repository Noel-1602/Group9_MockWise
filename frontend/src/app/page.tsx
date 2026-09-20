import Link from "next/link";

export default function Home() {
  return (
    <main>
      <h1>MockWise Frontend</h1>
      <p>Next.js 15 App Router Scaffolding</p>
      <nav>
        <ul>
          <li>
            <Link href="/upload">/upload</Link>
          </li>
          <li>
            <Link href="/interview/demo-session">/interview/demo-session</Link>
          </li>
          <li>
            <Link href="/report/demo-session">/report/demo-session</Link>
          </li>
        </ul>
      </nav>
    </main>
  );
}

