import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/Navigation";
import { Web3Provider } from "@/components/Web3Provider";
import { AuthGuard } from "@/components/AuthGuard";
import { ApolloProvider } from "@/components/ApolloProvider";

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
                    <p className="text-center text-sm text-gray-500">
                      All-Thing-Eye © 2025 | Tokamak Network
                    </p>
                  </div>
                </footer>
              </div>
            </AuthGuard>
          </Web3Provider>
        </ApolloProvider>
      </body>
    </html>
  );
}
