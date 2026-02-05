import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/Navigation";
import { Web3Provider } from "@/components/Web3Provider";
import { AuthGuard } from "@/components/AuthGuard";
import { ApolloProvider } from "@/components/ApolloProvider";
import FloatingAIChatbot from "@/components/FloatingAIChatbot";

export const metadata: Metadata = {
  title: "All-Thing-Eye | Team Activity Analytics",
  description: "Team member performance analysis and data visualization",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans">
        <ApolloProvider>
          <Web3Provider>
            <AuthGuard>
              <div className="min-h-screen bg-gray-50">
                {/* Navigation */}
                <Navigation />

                {/* Main content */}
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                  {children}
                </main>

                {/* Footer */}
                <footer className="bg-white border-t border-gray-200 mt-12">
                  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                      <p className="text-sm text-gray-500">
                        All-Thing-Eye © 2025 | Tokamak Network
                      </p>
                      <div className="flex items-center gap-4">
                        <a
                          href="https://github.com/tokamak-network/all-thing-eye"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors"
                          aria-label="GitHub Repository"
                        >
                          <svg
                            className="w-5 h-5"
                            fill="currentColor"
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                          >
                            <path
                              fillRule="evenodd"
                              d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                              clipRule="evenodd"
                            />
                          </svg>
                          <span className="text-sm">GitHub</span>
                        </a>
                        <a
                          href="https://github.com/tokamak-network/all-thing-eye/issues"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors"
                          aria-label="Report an Issue"
                        >
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          <span className="text-sm">Issues</span>
                        </a>
                      </div>
                    </div>
                  </div>
                </footer>

                {/* Floating AI Chatbot - Available on all pages */}
                <FloatingAIChatbot />
              </div>
            </AuthGuard>
          </Web3Provider>
        </ApolloProvider>
      </body>
    </html>
  );
}
