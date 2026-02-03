# Mehdi Notion 활동 누락 이슈 분석

## 문제 요약
- **보고자**: Mehdi
- **증상**: "Tokamak zkEVM Bridge" 문서를 작성했으나 ATI Activities에 표시 안됨
- **문서 위치**: `dev(internal) -> Ooo:Tokamak zk-EVM -> [Archive] Research notes of Tokamak zk-EVM`
- **문서 URL**: https://www.notion.so/tokamak/Tokamak-zkEVM-Bridge-Channel-Lifecycle-Technical-Specification-2f8d96a400a380a79951f948a0d4b1c0

## 원인 확정

**"collector" Integration이 해당 페이지에 접근 권한이 없음**

```
❌ 페이지 접근 실패: Could not find page with ID: 2f8d96a4-00a3-80a7-9951-f948a0d4b1c0. 
   Make sure the relevant pages and databases are shared with your integration.
```

### 확인된 사항

| 항목 | 상태 |
|------|------|
| Mehdi Notion 계정 | ✅ 존재 (ID: `7b27b658-9868-4de3-a519-a7f79b3eda70`) |
| ATI Integration 이름 | `collector` (Workspace: Tokamak Network) |
| "Ooo:Tokamak zk-EVM" 페이지 | ❌ API 검색에서 안 보임 |
| "Tokamak zkEVM Bridge" 페이지 | ❌ 직접 조회 시 접근 거부 |
| Dev (Internal) 아래 Ooo 페이지 | 0개 (Ooo:Tokamak zk-EVM은 Dev Internal 아래에 없음) |

### 데이터 수집 현황

| 컬렉션 | 최신 데이터 | Mehdi 기록 |
|--------|-------------|------------|
| notion_pages | 2026-01-16 | 54건 (이전 데이터) |
| notion_content_diffs | 2026-01-30 | 0건 |
| member_identifiers | - | Mehdi 없음 (매핑 미등록) |

## 해결 방법

### 1. Integration 연결 (Mehdi 또는 Workspace 관리자)

Mehdi가 "collector" Integration을 볼 수 없다고 함 (GitHub만 보임).

**옵션 A**: Workspace 관리자가 "Ooo:Tokamak zk-EVM" 영역에 collector Integration 공유
**옵션 B**: 문서를 Dev (Internal) 하위로 이동 (자동 권한 상속)

### 2. member_identifiers 등록 (추후)

Integration 연결 후, Mehdi의 Notion ID를 member_identifiers에 등록:
```javascript
{
  member_name: "Mehdi",
  source: "notion",
  identifier_value: "7b27b658-9868-4de3-a519-a7f79b3eda70"
}
```

## 다음 단계

1. [ ] Workspace 관리자에게 "Ooo:Tokamak zk-EVM" 페이지에 collector Integration 연결 요청
2. [ ] 또는 Mehdi가 문서를 Dev (Internal) 하위로 이동
3. [ ] Integration 연결 후 데이터 수집 확인
4. [ ] member_identifiers에 Mehdi Notion ID 등록

## 기술 정보

### Integration 정보
```json
{
  "name": "collector",
  "type": "bot",
  "workspace_name": "Tokamak Network",
  "workspace_id": "64903c51-687e-448d-8297-662b977d8aa9"
}
```

### 문서 페이지 ID
- Tokamak zkEVM Bridge: `2f8d96a4-00a3-80a7-9951-f948a0d4b1c0`

### Dev (Internal) 페이지 ID
- `c99da4fa-6d95-47aa-9f2d-a5dfa09a9c44`
