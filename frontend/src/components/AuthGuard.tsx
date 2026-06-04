'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAccount } from 'wagmi';
import { isSessionValid, getAuthSession, clearAuthSession } from '@/lib/auth';
import { isTokenValid, clearToken, getTokenTimeRemaining } from '@/lib/jwt';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isConnected } = useAccount();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Dev-only auth bypass — active ONLY when NEXT_PUBLIC_DEV_MODE=true (local .env.local).
  // Never true in production builds, so this does not weaken prod auth.
  const DEV_BYPASS = process.env.NEXT_PUBLIC_DEV_MODE === 'true';

  // Monitor wallet connection status
  useEffect(() => {
    // Skip for login page
    if (pathname === '/login') {
      return;
    }

    if (DEV_BYPASS) {
      return;
    }

    // If wallet is disconnected but we have auth tokens, logout
    if (!isConnected && (isTokenValid() || isSessionValid())) {
      console.log('🔌 Wallet disconnected, logging out...');
      clearToken();
      clearAuthSession();
      router.push('/login');
    }
  }, [isConnected, pathname, router, DEV_BYPASS]);

  useEffect(() => {
    // Skip auth check for login page
    if (pathname === '/login') {
      setIsLoading(false);
      return;
    }

    // Dev-only bypass: render the app without login when NEXT_PUBLIC_DEV_MODE=true
    if (DEV_BYPASS) {
      setIsAuthenticated(true);
      setIsLoading(false);
      return;
    }

    // Check authentication
    const checkAuth = () => {
      // Check JWT token first (primary authentication)
      const jwtValid = isTokenValid();
      
      // Fallback to old session check for backwards compatibility
      const sessionValid = isSessionValid();
      const session = getAuthSession();

      if (!jwtValid && (!sessionValid || !session)) {
        // Clear invalid authentication
        clearToken();
        clearAuthSession();

        console.log('🔒 Authentication invalid, redirecting to login');

        // Set loading to false before redirect to prevent infinite loading
        setIsLoading(false);
        setIsAuthenticated(false);

        // Redirect to login
        router.push('/login');
      } else {
        // Log token expiry time
        if (jwtValid) {
          const remaining = getTokenTimeRemaining();
          console.log(`✅ JWT token valid (expires in ${remaining} seconds)`);
        }

        setIsAuthenticated(true);
        setIsLoading(false);
      }
    };

    checkAuth();

    // Recheck every minute
    const interval = setInterval(checkAuth, 60000);

    return () => clearInterval(interval);
  }, [pathname, router, DEV_BYPASS]);

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

