/**
 * Web3 Wallet-based Admin Authentication
 *
 * Verifies admin access using Ethereum wallet signatures
 */

// Admin wallet addresses (화이트리스트)
// 환경 변수로 관리하거나 여기에 직접 추가
export const ADMIN_ADDRESSES = (process.env.NEXT_PUBLIC_ADMIN_ADDRESSES || "")
  .split(",")
  .map((addr) => addr.trim().toLowerCase())
  .filter((addr) => addr.length > 0);

// Fallback: 환경 변수가 없으면 여기서 관리
const HARDCODED_ADMINS = [
  // TODO: 실제 관리자 지갑 주소로 변경하세요!
  // 예시:
  "0xF9Fa94D45C49e879E46Ea783fc133F41709f3bc7",
  "0x322acfaa747f3ce5b5899611034fb4433f0edf34",
  "0x7f88539538ae808e45e23ff6c2b897d062616c4e",
  "0x9f1474b5b01940af4f6641bdcbcf8af3ca5197ec",
  "0x3d827286780dBc00ACE4ee416aD8a4C5dAAC972C",
  "0x6E1c4a442E9B9ddA59382ee78058650F1723E0F6",
  "0x248d48e44da385476072c9d65c043113a3839b91",
  "0xa4cb7fb1abb9d6f7750bddead7b11f7a3ec4ed10",
  "0xf109a6faa0c8adae8ccb114f4ab55d47e8fd4be6",
  "0x97826f4bf96EFa51Ef92184D7555A9Ac4DD7db80",
  "0xf90432b76A23bC7bB50b868dC4257C5F5B401742",
].map((addr) => addr.toLowerCase());

export const ALLOWED_ADMINS =
  ADMIN_ADDRESSES.length > 0 ? ADMIN_ADDRESSES : HARDCODED_ADMINS;

/**
 * Check if an address is an admin
 */
export function isAdmin(address: string | undefined): boolean {
  if (!address) return false;
  return ALLOWED_ADMINS.includes(address.toLowerCase());
}

/**
 * Generate a message to sign
 */
export function generateSignMessage(address: string): string {
  const timestamp = Date.now();
  return `Sign this message to authenticate as admin\n\nAddress: ${address}\nTimestamp: ${timestamp}\n\nThis signature will not trigger any blockchain transaction or cost any gas fees.`;
}

/**
 * Verify signature (client-side check)
 * Server-side verification should be done in production
 */
export async function verifySignature(
  address: string,
  signature: string,
  message: string
): Promise<boolean> {
  try {
    const { verifyMessage } = await import("viem");
    const isValid = await verifyMessage({
      address: address as `0x${string}`,
      message,
      signature: signature as `0x${string}`,
    });
    return isValid && isAdmin(address);
  } catch (error) {
    console.error("Signature verification failed:", error);
    return false;
  }
}

/**
 * Session storage keys
 */
export const AUTH_STORAGE = {
  ADDRESS: "auth_wallet_address",
  SIGNATURE: "auth_signature",
  MESSAGE: "auth_message",
  TIMESTAMP: "auth_timestamp",
} as const;

/**
 * Session duration (1 hour)
 */
export const SESSION_DURATION = 60 * 60 * 1000; // 1 hour in milliseconds

/**
 * Check if session is valid
 */
export function isSessionValid(): boolean {
  if (typeof window === "undefined") return false;

  const timestamp = localStorage.getItem(AUTH_STORAGE.TIMESTAMP);
  if (!timestamp) return false;

  const sessionAge = Date.now() - parseInt(timestamp);
  return sessionAge < SESSION_DURATION;
}

/**
 * Save auth session
 */
export function saveAuthSession(
  address: string,
  signature: string,
  message: string
): void {
  if (typeof window === "undefined") return;

  localStorage.setItem(AUTH_STORAGE.ADDRESS, address);
  localStorage.setItem(AUTH_STORAGE.SIGNATURE, signature);
  localStorage.setItem(AUTH_STORAGE.MESSAGE, message);
  localStorage.setItem(AUTH_STORAGE.TIMESTAMP, Date.now().toString());
}

/**
 * Clear auth session
 */
export function clearAuthSession(): void {
  if (typeof window === "undefined") return;

  Object.values(AUTH_STORAGE).forEach((key) => {
    localStorage.removeItem(key);
  });
}

/**
 * Get current auth session
 */
export function getAuthSession() {
  if (typeof window === "undefined") return null;

  const address = localStorage.getItem(AUTH_STORAGE.ADDRESS);
  const signature = localStorage.getItem(AUTH_STORAGE.SIGNATURE);
  const message = localStorage.getItem(AUTH_STORAGE.MESSAGE);
  const timestamp = localStorage.getItem(AUTH_STORAGE.TIMESTAMP);

  if (!address || !signature || !message || !timestamp) return null;

  return { address, signature, message, timestamp: parseInt(timestamp) };
}
