'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();

  const navItems = [
    { href: '/', label: 'Dashboard' },
    { href: '/members', label: 'Members' },
    { href: '/activities', label: 'Activities' },
    { href: '/projects', label: 'Projects' },
    { href: '/exports', label: '📥 Exports' },
  ];

  const isActive = (href: string) => {
    if (href === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(href);
  };

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
                      ? 'text-gray-900 border-primary-500'
                      : 'text-gray-500 hover:text-gray-900 border-transparent hover:border-gray-300'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center">
            <span className="text-sm text-gray-500">
              Team Analytics
            </span>
          </div>
        </div>
      </div>
    </nav>
  );
}

