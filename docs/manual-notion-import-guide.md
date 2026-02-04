# Manual Notion Page Import Guide

## 배경

Notion 페이지가 수집되지 않는 경우가 발생할 수 있습니다. 주로 다음과 같은 이유입니다:

1. **상위 페이지 접근 제한**: 페이지의 parent page가 Notion Integration에 공유되지 않은 경우
2. **수집 시점 이후 공유**: 페이지가 존재했지만 Integration 공유가 늦게 된 경우
3. **새로운 워크스페이스 영역**: Integration이 접근할 수 없는 새로운 영역에 페이지가 생성된 경우

## 해결 방법

### 1. Notion Integration 공유 설정 확인

1. 해당 페이지 또는 상위 페이지로 이동
2. 우측 상단 `...` → `Connections` 클릭
3. All-Thing-Eye Integration이 연결되어 있는지 확인
4. 없으면 추가

### 2. 수동 Import 스크립트 실행

```bash
# 스크립트 위치
scripts/manual_notion_import.py

# 실행
python scripts/manual_notion_import.py
```

### 3. 스크립트 수정 (필요시)

`scripts/manual_notion_import.py` 파일에서 다음 항목을 수정:

```python
# 1. Import할 페이지 ID 목록 (URL에서 마지막 32자리)
PAGE_IDS = [
    "2e2d96a400a380b3aec1f527fecaa019",  # 페이지 설명
    # ... 추가 페이지
]

# 2. 멤버 정보 (member_identifiers 테이블에서 확인)
MUHAMMED_NOTION_ID = "e7bba46f-b6ae-418a-9916-ffdab6fc75bc"
MUHAMMED_NAME = "Muhammed Ali Bingol"
MUHAMMED_EMAIL = "muhammed@tokamak.network"
```

## 페이지 ID 추출 방법

Notion URL 형식:
```
https://www.notion.so/tokamak/Page-Title-2e2d96a400a380b3aec1f527fecaa019
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        이 부분이 page_id (32자리)
```

## 스크립트가 하는 일

1. **notion_pages 컬렉션에 저장**: 페이지 메타데이터 및 컨텐츠
2. **notion_content_diffs 컬렉션에 저장**: 활동 API에서 조회되도록 diff 레코드 생성

## 데이터 확인

```python
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['ati']

# 특정 멤버의 Notion 페이지 확인
NOTION_USER_ID = 'e7bba46f-b6ae-418a-9916-ffdab6fc75bc'
pages = list(db.notion_pages.find({'created_by.id': NOTION_USER_ID}))
print(f'Total pages: {len(pages)}')

# 활동 diff 확인
diffs = list(db.notion_content_diffs.find({'editor_name': 'Muhammed'}))
print(f'Total diffs: {len(diffs)}')
```

## 2026-02-04 작업 기록 (Muhammed 케이스)

### 문제
- Muhammed의 Notion 활동이 All-Seeing-Eye에 표시되지 않음
- 원인: 상위 페이지(Ooo: Tokamak-zk-EVM)의 접근 제한

### 해결
1. 상위 페이지의 Integration 공유 설정 추가
2. 수동 import 스크립트로 11개 페이지 추가

### Import된 페이지 목록

| 페이지 | 생성일 |
|--------|--------|
| Bulletproofs: a Non-interactive Zero-knowledge proof scheme | 2026-02-03 |
| Golden: Lightweight Non-Interactive Distributed Key Generation | 2026-02-02 |
| TRH-SDK: Architecture & Security Analysis | 2026-01-26 |
| Algebraic Security Analysis of the Multi-Sig Aggregation | 2026-01-09 |
| Multi-Sig vs Threshold Signatures: Picking the Right one | 2026-01-08 |
| FROST threshold signature design for Tokamak zk-Rollup | 2025-09-18 |
| ECDSA and Schnorr base based threshold signature analysis | 2025-08-29 |
| MPC Ceremony Phase-1 summarizing report | 2025-08-28 |
| EdDSA over Jubjub (BlsScalar) with Poseidon Hash | 2025-08-15 |
| Baby JubJub Elliptic Curve Scheme | 2025-07-24 |
| Phase 1 MPC setup ceremony Docker based execution (combined) | 2025-07-16 |

### 멤버 식별자 정보

```
Member: Muhammed
Member ID: 697ad264b035090a61919512
Notion User ID: e7bba46f-b6ae-418a-9916-ffdab6fc75bc
Email: muhammed@tokamak.network
```
