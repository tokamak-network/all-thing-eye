'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { isSessionValid, getAuthSession, clearAuthSession } from '@/lib/auth';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Skip auth check for login page
    if (pathname === '/login') {
      setIsLoading(false);
      return;
    }

    // Check authentication
    const checkAuth = () => {
      const valid = isSessionValid();
      const session = getAuthSession();

      if (!valid || !session) {
        // Clear invalid session
        clearAuthSession();
        // Redirect to login
        router.push('/login');
      } else {
        setIsAuthenticated(true);
        setIsLoading(false);
      }
    };

    checkAuth();

    // Recheck every minute
    const interval = setInterval(checkAuth, 60000);

    return () => clearInterval(interval);
  }, [pathname, router]);

  // Show loading on login page
  if (pathname === '/login') {
    return <>{children}</>;
  }

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          <p className="mt-4 text-gray-600">Verifying authentication...</p>
        </div>
      </div>
    );
  }

  // Show children if authenticated
  if (isAuthenticated) {
    return <>{children}</>;
  }

  // Don't render anything while redirecting
  return null;
}

