"use client";

import { useState, useEffect } from "react";
import { useAccount, useConnect, useSignMessage, useDisconnect } from "wagmi";
import { useRouter, useSearchParams } from "next/navigation";
import {
  isAdmin,
  generateSignMessage,
  saveAuthSession,
  isSessionValid,
  ALLOWED_ADMINS,
} from "@/lib/auth";
import { storeToken, isTokenValid } from "@/lib/jwt";
import { api } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface OAuthProviders {
  google: boolean;
  github: boolean;
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { address, isConnected } = useAccount();
  const { connect, connectors } = useConnect();
  const { signMessageAsync } = useSignMessage();
  const { disconnect } = useDisconnect();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [oauthProviders, setOAuthProviders] = useState<OAuthProviders>({ google: false, github: false });
  const [oauthLoading, setOauthLoading] = useState<"google" | "github" | null>(null);

  // Handle OAuth callback (token from URL)
  useEffect(() => {
    const token = searchParams.get("token");
    const provider = searchParams.get("provider");
    const errorParam = searchParams.get("error");

    if (errorParam) {
      setError(`OAuth error: ${errorParam}`);
      // Clean up URL
      window.history.replaceState({}, document.title, "/login");
      return;
    }

    if (token && provider) {
      // Store the OAuth token
      const expiresIn = 60 * 60; // 1 hour default
      storeToken({
        access_token: token,
        token_type: "bearer",
        expires_in: expiresIn,
        address: "", // OAuth doesn't use address
        is_admin: true, // OAuth users are considered admins
      });

      console.log(`✅ OAuth login successful via ${provider}`);

      // Clean up URL and redirect
      window.history.replaceState({}, document.title, "/login");
      router.push("/");
    }
  }, [searchParams, router]);

  // Check if already authenticated
  useEffect(() => {
    if (isTokenValid()) {
      router.push("/");
    }
  }, [router]);

  // Fetch available OAuth providers
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/oauth/providers`);
        if (response.ok) {
          const data = await response.json();
          setOAuthProviders(data);
        }
      } catch (err) {
        console.error("Failed to fetch OAuth providers:", err);
      }
    };
    fetchProviders();
  }, []);

  const handleAuthenticate = async () => {
    if (!address) {
      setError("Please connect your wallet first");
      return;
    }

    // Check if admin (frontend validation)
    if (!isAdmin(address)) {
      setError(
        `Access denied. Your address (${address.slice(0, 6)}...${address.slice(
          -4
        )}) is not authorized.`
      );
      disconnect();
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Generate message to sign
      const message = generateSignMessage(address);

      // Request signature from wallet
      const signature = await signMessageAsync({ message });

      // Send signature to backend to get JWT token
      const tokenData = await api.login(address, message, signature);

      // Store JWT token
      storeToken(tokenData);

      // Also save old auth session for backwards compatibility
      saveAuthSession(address, signature, message);

      console.log("✅ Authentication successful", {
        address: tokenData.address,
        is_admin: tokenData.is_admin,
        expires_in: tokenData.expires_in,
      });

      // Redirect to dashboard
      router.push("/");
    } catch (err: any) {
      console.error("Authentication failed:", err);
      if (err.message?.includes("User rejected")) {
        setError(
          "Signature rejected. Please sign the message to authenticate."
        );
      } else if (err.response?.status === 403) {
        setError("Admin privileges required. Your address is not authorized.");
      } else if (err.response?.status === 401) {
        setError("Invalid signature. Please try again.");
      } else {
        setError("Authentication failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnectWallet = async () => {
    setError(null);
    try {
      const connector = connectors[0]; // MetaMask
      if (connector) {
        connect({ connector });
      }
    } catch (err) {
      console.error("Connection failed:", err);
      setError("Failed to connect wallet. Please install MetaMask.");
    }
  };

  const handleOAuthLogin = (provider: "google" | "github") => {
    setOauthLoading(provider);
    setError(null);
    // Redirect to OAuth endpoint - the backend will handle the OAuth flow
    const redirectUri = encodeURIComponent(window.location.origin + "/login");
    window.location.href = `${API_BASE_URL}/api/v1/oauth/${provider}/login?redirect_uri=${redirectUri}`;
  };

  return (
    <div className="fixed inset-0 bg-gray-800 flex items-center justify-center p-4 overflow-y-auto">
      <div className="max-w-md w-full my-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">👁️</div>
          <h1 className="text-3xl font-bold text-white mb-2">All-Thing-Eye</h1>
          <p className="text-gray-400">Admin Authentication</p>
        </div>

        {/* Login Card */}
        <div className="bg-gray-800 rounded-lg shadow-xl p-8 border border-gray-700">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-white mb-2">
              Connect Wallet to Continue
            </h2>
            <p className="text-sm text-gray-400">
              Only authorized admin wallets can access this application
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 bg-red-500/10 border border-red-500/50 rounded-lg p-4">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Connected Wallet Info */}
          {isConnected && address && (
            <div className="mb-6 bg-blue-500/10 border border-blue-500/50 rounded-lg p-4">
              <p className="text-sm text-gray-400 mb-1">Connected Wallet:</p>
              <p className="text-sm font-mono text-white break-all">
                {address}
              </p>
              {isAdmin(address) ? (
                <div className="mt-2 flex items-center text-green-400 text-sm">
                  <svg
                    className="w-4 h-4 mr-1"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Admin verified
                </div>
              ) : (
                <div className="mt-2 flex items-center text-red-400 text-sm">
                  <svg
                    className="w-4 h-4 mr-1"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Not authorized
                </div>
              )}
            </div>
          )}

          {/* OAuth Login Buttons */}
          {(oauthProviders.google || oauthProviders.github) && (
            <div className="space-y-3 mb-6">
              {oauthProviders.google && (
                <button
                  onClick={() => handleOAuthLogin("google")}
                  disabled={oauthLoading !== null}
                  className="w-full bg-white hover:bg-gray-100 text-gray-800 font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center border border-gray-300"
                >
                  {oauthLoading === "google" ? (
                    <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                  )}
                  Continue with Google
                </button>
              )}
              {oauthProviders.github && (
                <button
                  onClick={() => handleOAuthLogin("github")}
                  disabled={oauthLoading !== null}
                  className="w-full bg-gray-900 hover:bg-gray-800 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {oauthLoading === "github" ? (
                    <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
                      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                    </svg>
                  )}
                  Continue with GitHub
                </button>
              )}

              {/* Divider */}
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-600"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-gray-800 text-gray-400">or</span>
                </div>
              </div>
            </div>
          )}

          {/* Connect Button */}
          {!isConnected ? (
            <button
              onClick={handleConnectWallet}
              disabled={isLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              <svg
                className="w-5 h-5 mr-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
              Connect MetaMask
            </button>
          ) : (
            <div className="space-y-3">
              {isAdmin(address!) && (
                <button
                  onClick={handleAuthenticate}
                  disabled={isLoading}
                  className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {isLoading ? (
                    <>
                      <svg
                        className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        ></circle>
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        ></path>
                      </svg>
                      Signing...
                    </>
                  ) : (
                    <>
                      <svg
                        className="w-5 h-5 mr-2"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      Sign Message to Authenticate
                    </>
                  )}
                </button>
              )}
              <button
                onClick={() => disconnect()}
                className="w-full bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
              >
                Disconnect
              </button>
            </div>
          )}

          {/* Admin Addresses Info */}
          <div className="mt-6 pt-6 border-t border-gray-700">
            <details className="text-sm">
              <summary className="text-gray-400 cursor-pointer hover:text-gray-300">
                Authorized Admins ({ALLOWED_ADMINS.length})
              </summary>
              <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                {ALLOWED_ADMINS.map((addr, index) => (
                  <div
                    key={index}
                    className="font-mono text-xs text-gray-500 break-all"
                  >
                    {addr}
                  </div>
                ))}
              </div>
            </details>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>Secure Web3 authentication using wallet signatures</p>
        </div>
      </div>
    </div>
  );
}
