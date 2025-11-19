/**
 * JWT Token Management
 * 
 * Handles JWT token storage, retrieval, and validation
 */

const TOKEN_KEY = 'all_thing_eye_jwt_token';
const TOKEN_EXPIRY_KEY = 'all_thing_eye_jwt_expiry';

export interface JWTTokenData {
  access_token: string;
  token_type: string;
  expires_in: number;  // seconds
  address: string;
  is_admin: boolean;
}

/**
 * Store JWT token in localStorage
 */
export function storeToken(tokenData: JWTTokenData): void {
  if (typeof window === 'undefined') return;
  
  const expiryTime = Date.now() + tokenData.expires_in * 1000;
  
  localStorage.setItem(TOKEN_KEY, tokenData.access_token);
  localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());
  
  console.log('🔑 JWT token stored', {
    address: tokenData.address,
    expiresIn: `${tokenData.expires_in} seconds`,
    expiryTime: new Date(expiryTime).toISOString()
  });
}

/**
 * Get JWT token from localStorage
 */
export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  
  const token = localStorage.getItem(TOKEN_KEY);
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  
  // Check if token exists and is not expired
  if (!token || !expiry) {
    return null;
  }
  
  if (Date.now() > parseInt(expiry)) {
    console.warn('⏰ JWT token expired');
    clearToken();
    return null;
  }
  
  return token;
}

/**
 * Check if token is valid and not expired
 */
export function isTokenValid(): boolean {
  return getToken() !== null;
}

/**
 * Clear JWT token from localStorage
 */
export function clearToken(): void {
  if (typeof window === 'undefined') return;
  
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
  
  console.log('🗑️ JWT token cleared');
}

/**
 * Get time remaining until token expires (in seconds)
 */
export function getTokenTimeRemaining(): number {
  if (typeof window === 'undefined') return 0;
  
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  if (!expiry) return 0;
  
  const remaining = Math.max(0, parseInt(expiry) - Date.now());
  return Math.floor(remaining / 1000);
}

/**
 * Check if token will expire soon (within 5 minutes)
 */
export function isTokenExpiringSoon(): boolean {
  const remaining = getTokenTimeRemaining();
  return remaining > 0 && remaining < 300; // 5 minutes
}

/**
 * Get Authorization header value
 */
export function getAuthHeader(): string {
  const token = getToken();
  return token ? `Bearer ${token}` : '';
}

