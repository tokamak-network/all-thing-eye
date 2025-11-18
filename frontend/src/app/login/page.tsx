"use client";

import { useState, useEffect } from "react";
import { useAccount, useConnect, useSignMessage, useDisconnect } from "wagmi";
import { useRouter } from "next/navigation";
import {
  isAdmin,
  generateSignMessage,
  saveAuthSession,
  isSessionValid,
  ALLOWED_ADMINS,
} from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { address, isConnected } = useAccount();
  const { connect, connectors } = useConnect();
  const { signMessageAsync } = useSignMessage();
  const { disconnect } = useDisconnect();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check if already authenticated
  useEffect(() => {
    if (isSessionValid()) {
      router.push("/");
    }
  }, [router]);

  const handleAuthenticate = async () => {
    if (!address) {
      setError("Please connect your wallet first");
      return;
    }

    // Check if admin
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

      // Request signature
      const signature = await signMessageAsync({ message });

      // Save session
      saveAuthSession(address, signature, message);

      // Redirect to dashboard
      router.push("/");
    } catch (err: any) {
      console.error("Authentication failed:", err);
      if (err.message?.includes("User rejected")) {
        setError(
          "Signature rejected. Please sign the message to authenticate."
        );
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
