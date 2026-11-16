# Super Robot Wars OGs — 액셀 알마 역할 교체 패치

PS2 『슈퍼로봇대전 OG ORIGINAL GENERATIONS』의 라미아 아군 루트를 액셀로 플레이하는 패치입니다. **OGs 한글패치 v1.4.3s1 적용본**을 대상으로 합니다.

현재 버전: **v20261116**

[패처 ZIP 다운로드](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/v20261116/SRWOGS_AxelRoleSwap_kr_v20261116.zip) · [릴리즈](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/tag/v20261116) · [전체 변경내역](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/blob/main/CHANGELOG.md)


## 베오울프·Mk-Ⅲ HD 추가팩 (선택 설치)

[HD 추가팩 ZIP](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/v20261116/SRWOGS_Beowulf_MkIII_HD_Addon_v20261116.zip) · [설치·제거 안내](work_ogs/HD_INSTALL.txt)

PCSX2 텍스처 검색 폴더 아래 `SLPS-25733/replacements/beowulf_mk3`에 PNG 31개를 넣고 Graphics → Texture Replacement의 **Load Textures**를 켭니다. 기본 검색 경로라면 ZIP의 textures 폴더를 에뮬레이터 폴더에 합쳐 넣으세요. 기존 전체 HD팩은 포함하지 않으며 기존 replacements 폴더를 삭제하면 안 됩니다. 베오울프의 적 등장은 ISO 패처에서 별도로 켭니다. 자세한 설명은 ZIP의 설치방법.txt에도 있습니다.

파일: SRWOGS_Beowulf_MkIII_HD_Addon_v20261116.zip (22,594,476바이트)

SHA256: `8E469B518804C8E74FCD91963DF004F2EFF6D3708E967A5F5540876F5B20FCF3`

## 적용 방법

먼저 일본판 원본에 **OGs 한글패치 v1.4.3s1**을 적용한 뒤 이 액셀 역할 교체 패치를 적용하세요.

- [기준 한글패치 다운로드 — OGs-v1.4.3s1.7z](https://github.com/z3oo3z/PS2-SRWOGS-KPatch/releases/download/SRWOGS/OGs-v1.4.3s1.7z)
- [기준 한글패치 배포 페이지·안내](https://github.com/z3oo3z/PS2-SRWOGS-KPatch/releases/tag/SRWOGS) · [적용 안내](https://github.com/z3oo3z/PS2-SRWOGS-KPatch#readme)

적용 순서: **일본판 원본 → 한글패치 v1.4.3s1 → 액셀 역할 교체 패치**. 기준 한글패치는 별도 제작자가 배포하는 파일이며 이 패치 ZIP에는 포함하지 않습니다.

1. ZIP을 폴더째 풉니다.
2. `patcher/OGS_AxelSwap_QuickPatch.exe`에서 ISO를 선택합니다.
3. 원하는 옵션을 체크하고 [패치 적용]을 누릅니다. **여섯 옵션의 기본값은 모두 꺼짐**입니다.
4. 에뮬레이터를 완전히 다시 실행하고 **게임 내 메모리카드 세이브**로 불러옵니다. 이전 세이브 스테이트는 사용하지 마세요.

| 독립 선택 옵션 | 내용 |
|---|---|
| 숨겨진 요소 자동 습득 (OG2) | 획득 조건 해제·35화 바이사가 지급·35화 이후 미보유분 보충 |
| 오우카 생존 + 젠가 밸런스 | 44화 양쪽 루트 오우카 합류·45화 후속 대사, 다이젠가 강화·8무장 통합 |
| 자금 +20% · PP 2배 | 적 격추 보상 증가 |
| 적 강화 | 적 파일럿 6개 능력치 +5, 기체·무기 기본 개조 +2단, 기본 HP 20,000 미만 적 HP +10% |
| 액셀·제오라 정신기 변경 | 액셀 철벽·혼·각성 SP 조정, 제오라 번뜩임·가속 |
| 베오울프 등장 | 알피미와 함께 적 등장·추가 시나리오, 6화 시험 배치 제외 |

같은 ISO에서 체크를 바꾸고 재적용할 수 있습니다. 해제한 옵션의 패치 데이터는 원래대로 복원합니다. 이미 세이브에 쌓인 자금·PP·보유품·합류 기록은 회수하지 않습니다. 패처 옆 `.bin` 파일은 모두 함께 두세요. `.ogsbak`으로 마지막 작업 직전 상태를 복원할 수 있습니다.

기준 한글판 및 v20260831·v20260904·v20261002·v20261024·v20261025·v20261025.1·v20261026·v20261027·v20261027.1·v20261028·v20261029·v20261029.1·v20261101·v20261101.1·v20261102·v20261102.1·v20261105·v20261106 공개 적용본을 지원합니다. v20261026의 네 조합과 새 64개 조합 사이에서도 전환할 수 있습니다.

## 이번 업데이트

- 베오울프 파일럿 컷인을 이미지 생성으로 새로 제작했습니다. 두 종류의 원본 배치에 맞춰 등록하고, 외곽·투명 영역·부품 배치·UV 및 연출 명령은 유지했습니다.
- 일반 쿄스케 원본 컷인은 보존합니다. 베오울프 등장 옵션을 켠 경우에만 새 ISO 컷인이 적용됩니다.
- HD 추가팩도 같은 그림으로 갱신했습니다. 기체 16개·초상화 3개·컷인 및 호환 파일 12개, 총 PNG 31개입니다. 기존 ISO/새 ISO의 텍스처 파일명을 함께 지원합니다.
- 기존 여섯 옵션·바이사가 지급·입수 및 개수 이벤트·게임 밸런스를 유지합니다. 베오울프 OFF의 32개 ISO 결과는 v20261107과 동일합니다.

## 이번 버전 다운로드

- [ISO 패처 ZIP](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/v20261116/SRWOGS_AxelRoleSwap_kr_v20261116.zip)
- [HD 텍스처 이미지 세트 ZIP](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/v20261116/SRWOGS_Beowulf_MkIII_HD_Addon_v20261116.zip)

두 파일은 별도입니다. ISO나 전체 OGs HD팩은 포함하지 않습니다.

## 적용 방법

1. PCSX2를 종료합니다. 일본판 원본 → [한글패치 v1.4.3s1](https://github.com/z3oo3z/PS2-SRWOGS-KPatch/releases/download/SRWOGS/OGs-v1.4.3s1.7z) → 이 액셀 패치 순서로 적용합니다. 기존 공개 액셀 패치 적용본도 새 패처로 갱신할 수 있습니다.
2. ISO 패처 ZIP을 풀고 patcher/OGS_AxelSwap_QuickPatch.exe에서 ISO를 선택합니다. 원하는 옵션을 체크해 적용하세요. 베오울프를 사용하려면 ‘베오울프 등장’을 켭니다. 여섯 옵션 기본값은 모두 꺼짐입니다.
3. HD를 사용하는 분은 HD ZIP도 받으세요. 기존 beowulf_mk3 폴더는 텍스처 검색 폴더 밖에 백업한 뒤 새 파일로 교체합니다. 다른 replacements 폴더나 전체 HD팩은 유지하세요.
4. 기본 경로라면 HD ZIP의 textures 폴더를 에뮬레이터 폴더에 병합합니다. 최종 위치는 <검색 폴더>/SLPS-25733/replacements/beowulf_mk3/*.png입니다. PNG 파일명은 바꾸지 마세요.
5. Graphics → Texture Replacement → Load Textures를 켭니다. PCSX2 1.7.4005를 그대로 사용할 수 있으며 하드웨어 렌더러를 사용하세요. Dump Textures는 필요하지 않습니다.
6. 새로 부팅해 게임 내 메모리카드 세이브로 불러옵니다. ISO 갱신 후 예전 세이브 스테이트는 사용하지 마세요.

HD 제거 시 beowulf_mk3 폴더만 검색 폴더 밖으로 옮기면 됩니다. 자세한 안내는 HD ZIP의 설치방법.txt에 있습니다.

## 검증 범위

64개 옵션 결과 전체 SHA256, 컷인 외곽·알파·원본 리소스 보존, PNG 파일명·RGBA/GS 알파와 ZIP 무결성을 검사했습니다. 실제 모든 무장의 전투 연출을 새로 실플레이한 검증은 아닙니다.


## 기본 적용 사항

- **11화 잉그램·R-GUN 리바레 합류** 및 클리어 후 무기·강화파츠 5종 지급.
- **공통 21화 종료 후 발시온 개 지급**, 38화 종료 후 개수. 수리 전 주요 성능 약5% 저하·무장 −200, 개수 후 HP9000·EN300·장갑2100·운동성120으로 회복합니다.

- **아군 슬레이드겔미르** HP8300·장갑2100·6무장 공격력+200. 성체의태도 P/사거리1~2/배리어 관통. 적 원형은 유지합니다.
- **44화 마지막 결전 후 워단(W15)이 생환하여 슬레이드겔미르에 합류**합니다. 기존 기체와 개조값을 재사용하며 다른 탑승 파일럿 기록은 유지합니다. 오우카 생존 옵션과 별개로 기본 적용됩니다.
- **37화 클리어 후 그룬거스트 삼식**(젠가의 참식참함도 장착형)을 기체만 추가 지급합니다. 기존 다른 삼식은 유지하고 젠가 갈아타기를 지원합니다.
- OG2 **6화 종료 후 가리온 커스텀 무명**을 미보유한 경우 기체만 지급합니다. 5화 지급은 제거했습니다. 버려진 손상형을 회수하고 36화 종료 후 개수합니다.
- OG2 6화 클리어 후 **부스트 해머·시시오 블레이드·G 임팩트 스테이크·강철의 혼·용자의 증표·고성능 전자두뇌** 각각 1개 추가.
- OG2 37화 클리어 후 **슬레이드겔미르** 기체만 지급. 젠가 갈아타기 지원.
- 기존 소울게인·바이사가·아슈세이버 획득 및 갈아타기 조정 유지.
- 소울게인·바이사가 무장별 대사·음성 연결 수정, 시나리오 대사·호칭·문자 깨짐 교정, 적 라미아·안쥬르그 조정 유지.
- 아우센자이터 무장 공격력 +200 및 배리어 관통, 알트아이젠 리제 배리어 관통, 공용 시시오 블레이드·암검살·스태그 비틀 크래셔 사거리 조정 등 유지.

전체 수치와 획득 시점은 아래 누적 릴리즈 노트에 정리했습니다. **무명·리바레·발시온 개와 잉그램은 위 보충 지급을 지원합니다. 다른 지나간 화의 보상은 소급 지급하지 않습니다.** 오우카 생존은 44화 결말 이전부터 진행해야 합니다. 적 기본 개조는 적이 생성될 때 적용됩니다.

## xdelta

`SRWOGS_AxelRoleSwap_kr_v20261116.xdelta`는 기준 한글판 전용이며 여섯 옵션이 모두 꺼진 결과를 만듭니다. 워단 생존·삼식 추가 지급·무명 6화 지급은 모든 옵션 조합에 기본 적용됩니다.

```text
xdelta.exe -d -s "srwogs-v1.4.3s1.iso" "SRWOGS_AxelRoleSwap_kr_v20261116.xdelta" "출력.iso"
```

## 검증

64개 결과 ISO 전체 해시, 기존 5,120개 옵션 전환과 신규·이전 버전 40,960개 전환 경로, 실제 ISO 설치·업데이트·옵션 전환·백업 복원 22건을 검증했습니다. 전체 시나리오의 실플레이 검증을 새로 완료한 것은 아닙니다.

모든 조합의 ISO 크기는 4,518,150,144바이트입니다. 각 결과 해시는 ZIP의 `옵션별_ISO_SHA256.json`에 있습니다.

게임 ISO와 세이브는 배포하지 않습니다.
