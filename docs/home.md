<p class="badges">
  <img src="https://img.shields.io/badge/버전-v20260807-1e2a5a" alt="버전">
  <img src="https://img.shields.io/badge/플랫폼-PS2-a8871c" alt="플랫폼">
  <img src="https://img.shields.io/badge/형식-xdelta-informational" alt="형식">
  <img src="https://img.shields.io/badge/종류-역할교체 개조-success" alt="개조">
</p>

> ⬇️ **패치 다운로드**: [SRWOGS_AxelRoleSwap_kr_v20260807.xdelta](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/raw/main/patch/SRWOGS_AxelRoleSwap_kr_v20260807.xdelta) (약 5.17MB)

# 슈퍼로봇대전 OGs 액셀 역할 교체 패치

PS2용 **슈퍼로봇대전 OG ORIGINAL GENERATIONS**(スーパーロボット大戦OG ORIGINAL GENERATIONS)에서
라미아 로렐리스 루트를 **액셀 알마**(アクセル・アルマー)로 플레이하는 개조 패치입니다.

한국어 번역 패치가 아니라 **역할 교체 개조 패치**입니다. 기존 **OGs 한글패치 v1.4.3s1** 위에 얹어 씁니다.

> ※ 일본판 원본 ISO에는 적용되지 않습니다. 한글패치를 먼저 적용해 주세요.

## 한눈에 보기

| 항목 | 내용 |
|---|---|
| 대상 게임 | Super Robot Wars OG ORIGINAL GENERATIONS · PS2 |
| 적용 대상 | OGs 한글패치 **v1.4.3s1**이 적용된 ISO |
| 적용 전 크기 | 4,518,150,144 bytes |
| 적용 전 MD5 | `ef740dd41f5abcc05c6f6ba96ada9f5b` |
| 패치 형식 | xdelta (`.xdelta`) |
| 최신 버전 | **v20260807** (2026-08-07) |

> **이 저장소는 게임 ISO를 포함하지 않습니다.** xdelta 패치와 작업 스크립트만 배포합니다.

## 설치 및 적용

1. OGs 한글패치 v1.4.3s1이 적용된 ISO를 준비합니다. **(이 저장소는 ISO를 포함하지 않습니다.)**
   - 크기: 4,518,150,144 bytes
   - MD5: `ef740dd41f5abcc05c6f6ba96ada9f5b`
2. [패치 파일 `SRWOGS_AxelRoleSwap_kr_v20260807.xdelta`](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/raw/main/patch/SRWOGS_AxelRoleSwap_kr_v20260807.xdelta)을 내려받아 xdelta(또는 xdeltaUI, Delta Patcher 등)로 적용합니다.

   ```bash
   xdelta -d -s srwogs-v1.4.3s1.iso SRWOGS_AxelRoleSwap_kr_v20260807.xdelta srwogs-axel.iso
   ```
3. 적용 결과를 확인합니다 (선택).
   - 결과 크기: 4,518,150,144 bytes
   - 결과 MD5: `c44412acc77fd3536ab4cde072b2aaf6`

> 💡 GUI 툴만 쓰신다면 **xdeltaUI**에서 원본 ISO를 Source, 패치를 Patch로 지정하고 Apply Patch를 누르면 됩니다.
> 적용 전 해시가 위와 다르면 정상 적용되지 않습니다.

## 바뀌는 것

### 인물
- 라미아 로렐리스가 있던 자리에 **액셀 알마**가 들어갑니다.
- 액셀이 원래 있던 **적 자리에는 라미아**가 들어갑니다. 일방향이 아닌 **양방향 교환**입니다.
- 파일럿 데이터 · 초상화 · 상태창 · 이름 표기까지 함께 교체(PTbl 6엔트리 × SHARED/IM).

### 기체
| 슬롯 | 교체 전 | 교체 후 |
|---|---|---|
| 아군 | 안쥬르그 | **소울게인** |
| 적 | 소울게인 | **안쥬르그** |

적 보스의 HP는 원래 값(**18,928**)을 그대로 씁니다. 기체만 바꾸고 난이도는 건드리지 않았습니다.

### 이벤트 대사
- 대상 **3,245건 전수 대조**, **2,722 오프셋** 교체
- 이름 · 조사뿐 아니라 **상대가 부르는 호칭과 말투**까지 대응
  - 라미아의 존댓말 → 액셀의 반말
  - `엑세 누님` 같은 기존 개그와 액셀의 W 넘버 정체성은 보존
- 역할이 걸린 장면 **79개 전량 정독** 확인

### 전투 대사 · 음성
- **슈퍼로봇대전 A PORTABLE 한국어판**에서 액셀 대사·음성 이식 (클립 **185종**)
- ATRAC3+ → PCM → PS2 ADPCM 재인코딩 후 OGs 음성 뱅크(1046)에 재패킹
- 무기명이 나오는 대사는 **실제로 그 무기를 쏠 때만** 나오도록 배치
  - 현무강탄 → 「날아랏！ 현무강탄！！」 / 「로케트・소울 펀치！ 막 이래！」
- 기체 선택 전용 슬롯 **75개 복원** — 중반부터 소울게인改 · 바이사가 · 아슈세이버 ·
  라즈앙그리프를 골라 탈 수 있는데 원래 이 자리가 비어 있었습니다
  - 바이사가 — 「풍인섬！」 「이것이 오의・광인섬…！」
  - 아슈세이버 — 「할버트 런쳐、슛！」 「가라、소드 브레이커！」

## 알려진 한계

- **라즈앙그리프** 전용 무기(리볼빙 스테이크 · 벙커 · 트윈 빔 캐논)는 A PORTABLE에 액셀 음성이
  없어 무기명 없는 기합으로 대체했습니다.
- 본문이 `！`·`？` 뿐이라 물리적으로 늘릴 수 없는 5줄은 원문을 유지했습니다.
- 6화 대형 제목은 미대응입니다.
- 인게임 최종 확인이 끝나지 않았습니다. 기체별 전투 대사, 적 안쥬르그 등장 장면,
  7화 이후 시나리오에서 이상한 부분을 발견하시면 알려 주세요.

## 세이브 호환

세이브 파일 포맷은 변경하지 않았습니다. 다만 로스터에 기체가 기록되므로 **새로 시작**하시는 편이 안전합니다.

## 감사

- OGs 한글패치 v1.4.3s1 제작진
- 슈퍼로봇대전 A PORTABLE 한국어판 제작진 (액셀 대사 · 음성 원본)
