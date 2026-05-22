"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/obligations", label: "Contributions" },
  { href: "/profile", label: "Profile" },
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
      <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className="font-bold text-green-800 text-lg tracking-tight">Addis Kidan</span>
          <nav className="hidden sm:flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  pathname === link.href
                    ? "bg-green-50 text-green-800"
                    : "text-gray-600 hover:bg-gray-50"
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        {user && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 hidden sm:block">{user.full_name}</span>
            <Button variant="ghost" onClick={logout} className="text-xs px-3 py-1.5">
              Sign out
            </Button>
          </div>
        )}
      </div>
      {/* Mobile nav */}
      <nav className="sm:hidden flex border-t border-gray-100">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "flex-1 text-center py-2 text-xs font-medium",
              pathname === link.href ? "text-green-800 border-b-2 border-green-700" : "text-gray-500"
            )}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
