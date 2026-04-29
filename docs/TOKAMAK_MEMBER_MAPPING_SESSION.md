# Tokamak/Onther 멤버 실명-GitHub 매핑 세션 핸드오프

**마지막 업데이트**: 2026-04-23
**목표**: 2019-2023년 Tokamak Network / Onther 소속 멤버들의 **실명(한/영) ↔ GitHub username** 완전 매핑 구축

---

## 현재까지 진행 상황 요약

### 완료된 파이프라인
```
111,418 commits (raw tokamak_commits_2019_2023.csv)
  ↓ Phase A: GitHub isFork=true 외부 포크 49개 제외
 84,174 commits
  ↓ 외부 도메인 블랙리스트 (oplabs.co, uniswap.org 등)
 62,154 commits, 1,200 committers
  ↓ Phase B: disguised fork (tokamak-thanos, tokamak-titan 등) compare API 필터
 30,128 commits, 240 committers
  ↓ GitHub /users API + 이메일 + vault 교차 검증
 47 A_confirmed 멤버 실명 확보
```

### 3-소스 교차 검증
1. **GitHub /users/{login} API** — 1,128명 프로필 수집, 925명 실명 확보
2. **이메일 로컬파트 파싱** — 1,293 이메일 → 1,158 이름 힌트
3. **Obsidian vault 심층 스캔** — 172 힌트 (Medium/Slack/LinkedIn/이메일/서명)

### 확정된 47명 (전체 리스트는 `data/tokamak_member_identity_map.csv`)

**Onther 시대 (2019-2021)**:
- shingonu = Thomas S (Gonu), Jin/jins/jin.s = Jin S, Zena-park/zena/Zena = Zena Park
- ggs134 = Kevin Jeong, 4000D = Carl Park, dCanyon = Aiden Park
- Jake-Song = Jake Song (plasma), sifnoc = JinHwan, eric = Eric N, modagi = Seongjin Kim

**Tokamak Network 시대 (2021-2023)**:
- SonYoungsung = Son Youngsung (손영성)
- jason-h23 = Jason (alt: cd4761), Lakmi94 = Lakmi Kulathunga
- harryoh/Harry Oh = Harry Oh, Theo Lee/boohyung_lee/Theo = Boohyung Lee (이부형)
- zzooppii = HyukSang, steven94kr = Steven Lee, pleiadex = Sungyun Seo (Youn)
- nguyenzung = Nam Pham (Zung Nguyen), WyattPark = Wyatt Park
- JehyukJang = Jehyuk Jang PhD, usgeeus = Justin Gee
- suahnkim/Suah Kim = Suah Kim, kadirpili = Kadi Narmamatov
- jananadiw/Jananadi Wedagedara = Jananadi W, ohbyeongmin = Oh Byeongmin
- khk77 = hwisdom77, jusdy = Jupiter, jdhyun09 = donghyun
- code0xff = code0xff (@Haderech partner)

**도메인 필터로 제외됐지만 tokamak 멤버 (4명)**:
- KimKyungup = Ethan (Kyungup Kim, 김경업) — ECO Q1-Q2 2024 "Ethan"
- ehnuje = Melvin Junhee Woo (우준희) — OpenAsset contractor
- jeongkyun-oh = jk-jeongkyun (오정균)
- Jake Song = alias of Jake-Song

---

## 다음 세션에서 바로 할 일 (Priority Order)

### 1. Google Drive MCP로 2021-2023 월간/주간 보고서 처리 ⭐

**전제**: 재시작 후 MCP 도구 `mcp__claude_ai_Google_Drive__*` 가 실제로 로드됐는지 `ToolSearch`로 확인.

**받아둔 시트 URL들** (이전 세션에서 사용자가 공유):

#### 2021년
- 1월: https://docs.google.com/spreadsheets/d/1tQsPsUM3HZtqmaW1u44lyZN66DCXyiJIoq0Bm1eY27Q/edit#gid=667222075
- 2월: https://docs.google.com/spreadsheets/d/1SCiftRowpSBs1EdFd6rc8Auo5osteGuzTHQtlUuWF3A/edit#gid=617221251
- 3월: https://docs.google.com/spreadsheets/d/1dYDxHvNp5NYKAtVmZD_4kiLRWeALqPrvmVO-Eb23YMw/edit#gid=874235819
- 4월: https://docs.google.com/spreadsheets/d/1296Xopf1St8o51SaCXVPKsKTmBnP_nceE-cdu6H9410/edit#gid=1725393973
- 5월 주간: https://docs.google.com/spreadsheets/d/1_lswZg0JHjHP5EpQOBNCjocb5TLKysGiTwfbbZjs0c8/edit#gid=792369010
- 5월 월간: https://docs.google.com/spreadsheets/d/1dEQlyMyxCMNukqG5uW6Hoz6b1oeOCcFdJM_gIJcofBU/edit#gid=359473660
- 6월 주간: https://docs.google.com/spreadsheets/d/1-b5rE6iffznpFMYWxRmkD8IHnUesSa6yo1tntFz6jhw/edit#gid=0
- 6월 월간: https://docs.google.com/spreadsheets/d/139lRKoh1I1QQjKmk07tjfkbQWPN9EK_5BjDW2mT55fo/edit#gid=1925278060
- 7월 주간: https://docs.google.com/spreadsheets/d/1w3q4-NmJPCXCXgZh8dwPCe_eiqAdwQm3HU0JmHfOdKM/edit#gid=853727381
- 8월: https://docs.google.com/spreadsheets/d/1yAoQA1RsbQL7l55stetyyaJJpP4uD9HdphgJqKD-fTQ/edit#gid=792369010
- 9월: https://docs.google.com/spreadsheets/d/1oYMBxmk92d3SP4YzUzD5nvGG8x20o6Bwkq5bhCJn-g0/edit#gid=1675973794
- 10월: https://docs.google.com/spreadsheets/d/1DHbcj4K81RiK6h9MWE3522CqT_r9L9IDg9r4FwrrB7k/edit?gid=1092417729
- 11월: https://docs.google.com/spreadsheets/d/1X86oWLzN6m4fayaIyD55i5Cdyz0kUYGKn6ouZeMafVU/edit#gid=1092417729
- 12월: https://docs.google.com/spreadsheets/d/1lpZAJVwBOPaMebfTSb3Cca7XxWHrQkhTbt-h3YphsB8/edit#gid=1092417729

#### 2022년 (파일명만, URL은 사용자에게 재요청 필요)
- Weekly_Report_2022.Jan, Feb
- Monthly&Weekly Report_2022 Mar ~ Dec
- Demoday Summary for Biweekly Report

#### 2023년 (파일명만, URL은 사용자에게 재요청 필요)
- Monthly&Weekly Report_2023 Jan ~ Dec (DEV 버전 포함)
- DEV_2023 Jan
- zk-EVM_Individual performance indicators
- Tokamak Optimism Website Reporting
- TONStarter + TOSv2 Project Reporting
- L2 Economics Reporting
- Get Commits / Get Commits_zena
- 2023년 주간, 월간 성과 시트 (폴더)

**처리 방법**: 각 시트에서 아래 추출 → `data/google_sheets_rosters.csv`:
- 멤버 이름 (한/영)
- 담당 업무
- 활동 기간
- 이메일 / Slack 핸들
- GitHub 링크 (있으면)

**병합 방식**: `scripts/merge_sheets_into_identity_map.py` 작성해서 기존 `tokamak_member_identity_map.csv` 에 병합. 매핑 안 된 새 이름 발견 시 새 행 추가.

---

### 2. 남은 미매핑 vault 이름들 (25명) 최종 실명 확보

Vault에는 있지만 committer 아닌 사람들 (디자이너/PM/리서처):
- **ECO**: Ale, Ethan, Harvey (Harvey Jo), Justin (Justin Gee=usgeeus로 확정), Monica, Praveen (Praveen Surendran), Ryan, Lucas (Lucas Jung), Suhyeon
- **TRH**: Aaron (Aaron Lee), Austin (Austin O), Brave (Brave Nguyen), Lucas (Lucas Jung), Max, Nam (Nam Pham=nguyenzung), Praveen, Theo (=Boohyung Lee), Victor
- **DRB**: Dragan, Kaiden, Kyle (Kyle Huang)
- **zk-EVM 2024+**: Aamir, Daniel, Dragan, Jamie, Kyros, Luca, Mehdi (Mehdi Tokamak=mehdi-defiesta), Mohammad, Monica, Muhammed (Muhammed Ali Bingol=mabingol), Nil (Nil Soroush PhD), S. Seo (=pleiadex)
- **SYB**: Jamie

Google Sheets에서 나올 정보로 상당수 해결될 것.

---

### 3. 불완전한 실명 보강

GitHub bio 없어서 정보 부족한 사람:
- Jake-Song (그냥 "Jake Song"), khk77 (hwisdom77), jusdy (Jupiter), jdhyun09 (donghyun)
- HyukSang (zzooppii) — 성씨 불명
- JinHwan (sifnoc) — 성씨 불명

---

## 파일 위치 (모두 `/Users/son-yeongseong/Desktop/dev/all-thing-eye/` 기준)

### 스크립트 (모두 작동 확인됨)
- `scripts/filter_fork_commits.py` — Phase A: GitHub isFork 필터
- `scripts/exclude_by_domain.py` — 외부 도메인 블랙리스트 필터
- `scripts/phase_b_disguised_fork_filter.py` — disguised fork compare API
- `scripts/committer_profile.py` — committer 프로필 생성
- `scripts/classify_committers.py` — Tier A/B/C/D 분류
- `scripts/match_vault_members.py` — 초기 vault 매칭
- `scripts/build_member_registry.py` — 기본 레지스트리 (v1)
- `scripts/enrich_github_profiles.py` — GitHub /users API (캐시 지원)
- `scripts/extract_email_name_hints.py` — 이메일 이름 힌트
- `scripts/build_identity_map.py` — **최종 통합** ⭐

### 데이터 (`data/`)
- ⭐ **`tokamak_member_identity_map.csv`** — 최종 매핑 (47 A_confirmed)
- `tokamak_commits_2019_2023_final.csv` — Phase B 후 커밋 (30K)
- `tokamak_commits_2019_2023_clean.csv` — Phase A+도메인 필터 (62K)
- `tokamak_commits_2019_2023_filtered.csv` — Phase A만 (84K)
- `tokamak_team_rosters.csv` — 141행 팀×분기 로스터 (ECO/DRB/SYB/TRH/zk-EVM)
- `vault_identity_hints.csv` — 172 vault 힌트
- `github_profiles.csv` — 1,128명 GitHub 프로필
- `github_profiles_cache.json` — API 응답 캐시 (재실행 시 재사용)
- `email_name_hints.csv` — 1,293 이메일 파싱
- `committer_classification.csv` — Tier 분류
- `committer_profiles_clean.csv` / `committer_profiles.csv`
- `upstream_shas_cache.json` — Phase B upstream SHA 캐시
- `tokamak_members_registry.csv` — 구버전 레지스트리 (build_member_registry.py 출력)
- `excluded_committers_by_domain.csv` — 도메인 필터에 걸린 80명
- `tokamak_commits_2019_2023_excluded.csv` — Phase A에서 제외된 27K 커밋

### 참조 경로
- **Obsidian vault**: `/Users/son-yeongseong/Desktop/obsidian/Tokamak Network/`
  - 주요: `Migration from Notion/ECO/ECO Tokamak Economics/Monthly report(previous)/`
  - `Migration from Notion/OOO Tokamak zk-EVM/Archive Personal progress reports/`
  - `Migration from Notion/TRH/TRH Tokamak Rollup Hub/team-structure.md`

### 주요 환경변수 (.env)
- `GITHUB_TOKEN` — GitHub API 호출용 (Phase B, enrichment)
- `GITHUB_ORG=tokamak-network`

---

## 재시작 후 첫 번째 프롬프트 제안

```
docs/TOKAMAK_MEMBER_MAPPING_SESSION.md 읽어서 상황 파악하고,
Google Drive MCP로 2021년 1월 시트부터 순회해서
팀원 로스터 추출한 다음 tokamak_member_identity_map.csv에 병합해줘.
```

---

## 세션 내내 확인된 핵심 통찰

1. **Onther-Tech → tokamak-network 이전**은 깔끔하게 됐음. 옛날 org 데이터 이미 다 포함.
2. **tokamak-thanos** 는 compare API로 필터 시 0.8%만 제거됨 — rebase로 SHA 완전히 바뀜. author 기반 추가 필터가 필요할 수 있음 (현재는 미적용).
3. **공통 이름 GitHub login 주의** (Jin, Theo, eric, Jason 등) — /users/{name} 결과가 전혀 다른 사람일 수 있음. 이메일(@onther.io)로 교차 검증 필수.
4. **한 사람 = 여러 committer_id** 매우 흔함:
   - Jin/jins/jin.s/jin.makerDao/jin_Dockeer/jinsDocker/jinsMBP/jins.docker — 같은 사람 8개 alias
   - Zena-park/zena/Zena — 같은 사람
   - Theo Lee/boohyung_lee/Theo — 같은 사람
   - jananadiw/Jananadi Wedagedara — 같은 사람
   - Jake-Song/Jake Song — 같은 사람
5. **disguised fork 식별 목록**: tokamak-thanos, tokamak-thanos-geth, tokamak-titan, tokamak-titan-explorer, tokamak-optimism-blockscout, cbdc-optimism(-old), tokamak-uniswap-v3-{core,periphery,interface}, tokamak-swap-router-contracts, tokamak-uniswap-subgraph, tokamak-graph-node, plasma-evm, klaytn-for-testing
6. **GitHub 조직 플랜**: tokamak-network = **Team** plan (NOT Enterprise Cloud) → audit-log API 404. 따라서 과거 멤버십 공식 복원 불가.
