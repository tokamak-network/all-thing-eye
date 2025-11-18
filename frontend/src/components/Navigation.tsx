"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getAuthSession, clearAuthSession } from "@/lib/auth";

export default function Navigation() {
  const pathname = usePathname();
  const router = useRouter();
  const [walletAddress, setWalletAddress] = useState<string | null>(null);

  useEffect(() => {
    const session = getAuthSession();
    if (session) {
      setWalletAddress(session.address);
    }
  }, []);

  const navItems = [
    { href: "/", label: "Dashboard" },
    { href: "/database", label: "🗄️ Database" },
    { href: "/exports", label: "📥 Exports" },
    { href: "/custom-export", label: "🎨 Custom Export" },
    { href: "/activities", label: "Activities" },
    { href: "/members", label: "Members" },
  ];

  const isActive = (href: string) => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname.startsWith(href);
  };

  const handleLogout = () => {
    clearAuthSession();
    router.push("/login");
  };

  // Don't show navigation on login page
  if (pathname === "/login") {
    return null;
  }

  return (
    <nav className="bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <Link
              href="/"
              className="flex items-center px-2 py-2 text-xl font-bold text-primary-600"
            >
              👁️ All-Thing-Eye
            </Link>
            <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`inline-flex items-center px-1 pt-1 text-sm font-medium border-b-2 transition-colors ${
                    isActive(item.href)
                      ? "text-gray-900 border-primary-500"
                      : "text-gray-500 hover:text-gray-900 border-transparent hover:border-gray-300"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {walletAddress && (
              <div className="hidden md:flex items-center space-x-2 text-sm">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-600 font-mono">
                  {walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}
                </span>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <svg
                className="w-4 h-4 mr-1"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
