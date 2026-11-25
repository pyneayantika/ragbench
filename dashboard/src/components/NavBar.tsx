"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/failures", label: "Where it breaks" },
  { href: "/examples", label: "Failure examples" },
  { href: "/method", label: "Method" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="nav-bar">
      <div className="nav-inner">
        <Link href="/" className="brand">
          RAG<span>Bench</span>
        </Link>
        <nav className="nav-links" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${active ? " active" : ""}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
