# 🔐 Web3 Wallet Authentication Setup

지갑 서명 기반 관리자 인증 설정 가이드

---

## 📋 목차

1. [개요](#개요)
2. [패키지 설치](#패키지-설치)
3. [관리자 주소 설정](#관리자-주소-설정)
4. [테스트](#테스트)
5. [배포](#배포)
6. [FAQ](#faq)

---

## 🎯 개요

### 인증 방식

```
1. 사용자가 MetaMask 지갑 연결
2. 지갑 서명 요청 (가스비 없음)
3. 서명 검증 + 관리자 주소 확인
4. 세션 생성 (1시간 유효)
5. 인증된 사용자만 애플리케이션 접근 가능
```

### 보안 특징

- ✅ **가스비 없음**: 서명만 사용 (트랜잭션 없음)
- ✅ **화이트리스트 기반**: 등록된 관리자 주소만 접근 가능
- ✅ **세션 관리**: 1시간 자동 만료
- ✅ **클라이언트 검증**: 빠른 응답 속도
- ⚠️ **주의**: 프로덕션에서는 서버 검증 추가 권장

---

## 📦 패키지 설치

### 필수 패키지

```bash
cd frontend
npm install wagmi viem @tanstack/react-query
```

### 버전 확인

```json
{
  "wagmi": "^2.x.x",
  "viem": "^2.x.x",
  "@tanstack/react-query": "^5.x.x"
}
```

---

## 🔑 관리자 주소 설정

### Option 1: 환경 변수 (권장)

`frontend/.env.local` 파일 생성:

```bash
# Admin wallet addresses (comma-separated, lowercase)
NEXT_PUBLIC_ADMIN_ADDRESSES=0x742d35cc6634c0532925a3b844bc9e7595f0beb,0x1234567890123456789012345678901234567890
```

**주의사항:**
- 주소는 **소문자**로 입력
- 쉼표로 구분 (공백 가능)
- `0x` 접두사 필수
- `.env.local`은 git에 커밋하지 않음

### Option 2: 코드에 직접 설정

`frontend/src/lib/auth.ts` 수정:

```typescript
const HARDCODED_ADMINS = [
  '0x742d35cc6634c0532925a3b844bc9e7595f0beb',  // Jake
  '0x1234567890123456789012345678901234567890',  // Jason
  '0xabcdefabcdefabcdefabcdefabcdefabcdefabcd',  // Jamie
].map(addr => addr.toLowerCase());
```

### 관리자 주소 확인 방법

#### MetaMask에서 확인

1. MetaMask 확장 프로그램 열기
2. 계정 이름 클릭
3. "Account details" 클릭
4. 주소 복사 (예: `0x742d35...`)

#### 이더스캔에서 확인

```
https://etherscan.io/address/YOUR_ADDRESS
```

---

## 🧪 테스트

### 1. 로컬 개발 서버 실행

```bash
cd frontend
npm run dev
```

### 2. 브라우저 접속

```
http://localhost:3000
```

### 3. 자동 리다이렉트

- 인증되지 않은 사용자 → `/login` 페이지로 이동
- 인증된 사용자 → `/` 대시보드

### 4. 로그인 테스트

#### ✅ 성공 케이스

```
1. MetaMask 설치됨
2. 지갑 주소가 관리자 리스트에 있음
3. "Connect MetaMask" 클릭
4. "Sign Message to Authenticate" 클릭
5. MetaMask에서 서명 승인
→ 대시보드로 이동 ✅
```

#### ❌ 실패 케이스

**Case 1: 관리자 아닌 주소**
```
- 연결 성공
- "Not authorized" 표시
- 접근 거부
```

**Case 2: 서명 거부**
```
- "Signature rejected" 에러 메시지
- 로그인 페이지 유지
```

**Case 3: MetaMask 미설치**
```
- "Failed to connect wallet" 에러
- MetaMask 설치 안내
```

### 5. 세션 테스트

```bash
# 브라우저 DevTools Console에서
localStorage.getItem('auth_wallet_address')
localStorage.getItem('auth_timestamp')

# 세션 만료 테스트 (1시간 후)
# 또는 강제 만료:
localStorage.removeItem('auth_timestamp')
# 페이지 새로고침 → /login으로 리다이렉트
```

---

## 🚀 배포

### Docker 환경 변수 설정

`docker-compose.prod.yml`:

```yaml
services:
  frontend:
    environment:
      - NEXT_PUBLIC_ADMIN_ADDRESSES=${ADMIN_ADDRESSES}
```

`.env` 파일:

```bash
ADMIN_ADDRESSES=0x742d35cc6634c0532925a3b844bc9e7595f0beb,0x1234567890123456789012345678901234567890
```

### AWS Secrets Manager (권장)

```bash
# 시크릿 생성
aws secretsmanager create-secret \
  --name all-thing-eye/admin-addresses \
  --secret-string '["0x742d35cc6634c0532925a3b844bc9e7595f0beb","0x123..."]'

# 배포 스크립트에서 가져오기
ADMIN_ADDRESSES=$(aws secretsmanager get-secret-value \
  --secret-id all-thing-eye/admin-addresses \
  --query SecretString \
  --output text)
```

### Nginx 설정

Nginx 프록시를 통해 환경 변수 전달 필요 없음 (빌드 타임에 번들링됨)

### 빌드 확인

```bash
cd frontend
npm run build

# 빌드된 환경 변수 확인
grep -r "NEXT_PUBLIC_ADMIN" .next/
```

---

## 🔒 보안 권장사항

### 1. 서버 사이드 검증 추가

현재는 클라이언트에서만 검증. 프로덕션에서는 백엔드 검증 추가:

```python
# backend/api/v1/auth.py
from eth_account.messages import encode_defunct
from web3 import Web3

def verify_signature(address: str, message: str, signature: str):
    w3 = Web3()
    message_hash = encode_defunct(text=message)
    recovered = w3.eth.account.recover_message(message_hash, signature=signature)
    return recovered.lower() == address.lower()
```

### 2. 타임스탬프 검증

서명 메시지에 포함된 타임스탬프가 최근인지 확인:

```typescript
const MESSAGE_VALIDITY = 5 * 60 * 1000; // 5분

function isMessageRecent(timestamp: number): boolean {
  return Date.now() - timestamp < MESSAGE_VALIDITY;
}
```

### 3. HTTPS 필수

프로덕션에서는 반드시 HTTPS 사용:

```bash
# Certbot으로 SSL 인증서 발급
sudo certbot --nginx -d your-domain.com
```

### 4. Rate Limiting

로그인 시도 제한:

```typescript
// 간단한 클라이언트 rate limiting
const MAX_ATTEMPTS = 5;
const LOCKOUT_TIME = 15 * 60 * 1000; // 15분
```

### 5. 정기 관리자 주소 감사

```bash
# 매월 관리자 주소 리스트 검토
# 퇴사자 제거, 신규 관리자 추가
```

---

## 📱 지원 지갑

### 현재 지원

- ✅ **MetaMask** (데스크톱 & 모바일)
- ✅ **MetaMask Mobile** (WalletConnect)

### 추가 지갑 지원 (선택)

```bash
npm install @rainbow-me/rainbowkit
```

```typescript
// frontend/src/components/Web3Provider.tsx
import { RainbowKitProvider } from '@rainbow-me/rainbowkit';
import { metaMask, walletConnect, coinbaseWallet } from 'wagmi/connectors';

const config = createConfig({
  connectors: [
    metaMask(),
    walletConnect({ projectId: 'YOUR_PROJECT_ID' }),
    coinbaseWallet({ appName: 'All-Thing-Eye' }),
  ],
  // ...
});
```

---

## ❓ FAQ

### Q1: MetaMask가 없으면 어떻게 하나요?

**A:** MetaMask 설치 안내:
```
1. 크롬/파이어폭스 확장 프로그램 스토어에서 "MetaMask" 검색
2. 설치 후 지갑 생성 또는 복구
3. 관리자에게 지갑 주소 전달
```

### Q2: 모바일에서도 작동하나요?

**A:** 네, 두 가지 방법:
1. MetaMask 모바일 앱 내장 브라우저 사용
2. WalletConnect 연동 (추가 개발 필요)

### Q3: 서명 시 가스비가 드나요?

**A:** 아니오, 서명만 하므로 **가스비 0원**입니다.

### Q4: 세션이 자꾸 만료돼요

**A:** 현재 세션 유효 시간: **1시간**

연장하려면 `frontend/src/lib/auth.ts` 수정:

```typescript
export const SESSION_DURATION = 8 * 60 * 60 * 1000; // 8시간
```

### Q5: 관리자 주소를 추가하려면?

**A:** 두 가지 방법:

**방법 1: 환경 변수 (재시작 필요)**
```bash
# .env.local 수정
NEXT_PUBLIC_ADMIN_ADDRESSES=0xold,0xnew
# 서버 재시작
npm run dev
```

**방법 2: 코드 수정 (재빌드 필요)**
```typescript
// src/lib/auth.ts
const HARDCODED_ADMINS = [
  '0xold',
  '0xnew', // 추가
];
```

### Q6: 테스트넷에서도 작동하나요?

**A:** 네, 서명은 네트워크 무관합니다. Mainnet, Sepolia, Goerli 모두 가능.

### Q7: 서명 메시지를 커스터마이즈하려면?

**A:** `frontend/src/lib/auth.ts` 의 `generateSignMessage` 함수 수정:

```typescript
export function generateSignMessage(address: string): string {
  return `Welcome to All-Thing-Eye!\n\n` +
         `Sign to verify your identity.\n` +
         `Address: ${address}\n` +
         `Time: ${new Date().toISOString()}`;
}
```

---

## 🔄 업그레이드 로드맵

### Phase 1 (완료) ✅
- 지갑 연결 + 서명 기반 인증
- 화이트리스트 관리자 주소
- 1시간 세션 관리

### Phase 2 (계획)
- 서버 사이드 서명 검증
- JWT 토큰 발급
- 리프레시 토큰

### Phase 3 (계획)
- 역할 기반 접근 제어 (RBAC)
- 관리자 / 뷰어 / 에디터 권한
- 활동 로그 추적

### Phase 4 (계획)
- 다중 지갑 지원 (RainbowKit)
- 소셜 로그인 (Web3Auth)
- 2FA 추가 인증

---

## 📞 문의

**문제 발생 시:**
1. 브라우저 콘솔 확인 (F12)
2. MetaMask 연결 상태 확인
3. 관리자 주소 리스트 확인
4. 이슈 생성 또는 팀 문의

---

**마지막 업데이트:** 2025-11-12  
**버전:** 1.0.0  
**작성자:** All-Thing-Eye Development Team

