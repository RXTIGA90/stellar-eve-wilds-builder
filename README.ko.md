<p align="center">
  <img src="data/ui/header.png" width="150" alt="Stellar Eve 아이콘">
</p>

<h1 align="center">스텔라 이브 for 몬스터 헌터 와일즈</h1>

<p align="center">
  몬헌 와일즈를 스텔라 블레이드의 이브와 이브 의상 22벌로 오프라인 플레이하는 모드입니다.<br>
  내 PC의 두 게임에서 직접 만들어 설치하며, 게임 파일은 들어 있지 않습니다.<br>
  <a href="README.md">English</a> · <b>한국어</b>
</p>

<p align="center">
  <img src="data/previews/27.jpg" width="96" alt="27"> <img src="data/previews/144.jpg" width="96" alt="144"> <img src="data/previews/150.jpg" width="96" alt="150"> <img src="data/previews/152.jpg" width="96" alt="152"> <img src="data/previews/153.jpg" width="96" alt="153"> <img src="data/previews/158.jpg" width="96" alt="158">
</p>

> **빠른 시작:** **Code > Download ZIP** → 압축 풀기 → 게임 끄기 → **`install.bat`** 더블클릭 →
> 언어 선택 → 의상 체크 → **설치**. 지울 때는 **Stellar Eve 제거** ([제거](#제거) 참고).


## 작동 방식
1. 설치 프로그램이 변환 도구(Blender, RE Mesh Editor 등)를 공식 배포처에서 받습니다.
2. 여러분 PC의 스텔라 블레이드에서 이브의 몸·얼굴·머리카락·의상을, 몬헌 와일즈에서 바꿀 갑옷 파일을 꺼냅니다.
3. Blender에서 이브 모델을 헌터 뼈대에 맞게 옮기고(자세·가중치·물리), 몬헌 형식(mesh·mdf2·tex·chain2)으로 저장합니다.
4. 만든 파일을 그 갑옷 자리에 넣습니다(바뀌는 원본은 먼저 백업).
5. 게임 안에서는 REFramework 스크립트가 이브 의상을 입었을 때만 얼굴을 이브로 바꾸고, 체형(관절 위치)을 이브에 맞추고,
   겹치는 다른 방어구(투구 제외)를 숨깁니다. 다른 갑옷으로 갈아입으면 원래 헌터로 돌아갑니다.
6. 3번 단계에서 게임으로 확인한 최종 외형(공통 피부색, 목 경계, 의상 수정)을 `data/repro`로 다시 입힙니다.
   숫자 데이터(정점 위치·법선·가중치 차이, 재질 노드 레시피, 일부 설정 변경)만 들어 있고 게임·스텔라 블레이드 데이터는 없습니다.
   재질 레시피는 여러분의 스텔라 블레이드 파일로 텍스처에 구워집니다(`scripts/eve_repro*.py`).

## 필요한 것
- Steam판 **스텔라 블레이드**, **몬스터 헌터 와일즈** (설치 드라이브는 상관없음)
- **REFramework**: [REFramework-nightly 릴리스](https://github.com/praydog/REFramework-nightly/releases)의 `REFramework.zip` 안 `dinput8.dll`을
  `MonsterHunterWilds.exe`가 있는 폴더에 넣습니다.
- 빈 공간 약 25GB, 인터넷(필요한 도구를 자동으로 받음)

## 설치
1. 이 페이지에서 **Code > Download ZIP**(항상 최신 버전, 전체 의상이 들어 있음, 약 2MB)을 받아 한글·공백 없는 폴더(예: `D:\stellar-eve`)에 풉니다.
2. 몬헌을 끄고 **`install.bat`을 더블클릭**합니다.
   `install.bat`은 이 폴더에 들어 있는 소스(`tools\launcher\StellarEve.cs`)를 Windows에 기본으로 있는 .NET 컴파일러로
   `StellarEve.exe`로 만들어 실행합니다. 미리 만든 실행 파일을 받지 않으니, 소스를 직접 읽어 보고 확인할 수 있습니다.
   - **"게시자를 확인하지 못했습니다" 보안 경고**가 뜨면 **실행**을 누르세요. 인터넷에서 받은 ZIP의 파일에 Windows가 붙이는 표시 때문이며,
     서명 없는 배치 파일이면 항상 뜹니다. 첫 실행 때 이 폴더의 표시를 지우므로 다음부터는 뜨지 않습니다.
     처음부터 안 뜨게 하려면 풀기 전에 ZIP 파일 우클릭 → **속성** → 아래 **차단 해제** 체크 → 확인 후 풉니다.
3. **언어(한국어 / English)를 고릅니다.** 이후 모든 화면, 의상 이름, 갑옷 이름이 그 언어로 나옵니다(홈 화면의 `Language / 언어`로 언제든 바꿀 수 있음).
   홈 화면 아래 **설치 전 점검**에서 몬헌 와일즈, REFramework, 스텔라 블레이드, 빈 공간, 폴더 경로를 자동으로 확인합니다.
   - 빨간 ✖: 설치할 수 없음. 게임을 못 찾았으면 **폴더 선택**으로 직접 고르세요(Steam이 아닌 위치도 됨).
   - 주황 !: 설치는 되지만 확인 필요. REFramework가 없으면 **받는 곳** 버튼이 받는 페이지를 엽니다.
4. **설치 / 의상 추가**를 누르면 의상 사진 창이 열립니다. 카드마다 이브 의상 이름(스텔라 블레이드 공식 이름), 몬헌에서 입을 갑옷 이름,
   외형 메뉴 위치, 필요한 DLC가 나옵니다. **원하는 의상에 체크**하고 **설치**를 누릅니다(사진을 눌러도 체크됩니다, 전부면 **전체 선택**).
   - `동시 빌드`: 한 번에 만들 벌 수(PC가 좋으면 3). `바탕화면·시작 메뉴 바로가기`: 체크하면 `Stellar Eve` 바로가기를 만듭니다.
5. 진행률 창에서 **퍼센트와 현재 단계**가 보입니다. 끝나면 `완료! 게임을 켜세요.`가 나옵니다.
   게임에서 아래 표의 **갑옷을 외형(덧입기)으로** 입으면 그 의상이 나옵니다(그 갑옷을 게임에서 만들어 둬야 외형 목록에 나옵니다).

- 한 벌만 원해도 ZIP은 같은 것을 받으면 됩니다(의상 데이터는 숫자만이라 작습니다). 메뉴에서 그 번호 하나만 고르세요.
- [Releases](https://github.com/RXTIGA90/stellar-eve-wilds-builder/releases)의 최신 릴리스에 있는 **Source code (zip)**도 같은 파일입니다. 가장 최신은 항상 **Code > Download ZIP**입니다.
- **나중에 의상 추가**: `Stellar Eve` 바로가기(또는 `install.bat`)를 다시 실행해 추가할 의상만 체크합니다. 먼저 넣은 의상은 그대로 남습니다.
- 창 없이(텍스트 모드): `install.bat -Rows 158,147`(표의 번호), `install.bat -All`, 번호 목록: `install.bat -NoGui`.
  이 경우에만 PowerShell 창(`install.ps1`)이 보입니다. 창 모드에서도 실제 작업은 같은 `install.ps1`이 하며, 그 출력은 진행률 창의 로그와 `install_log.txt`에 그대로 나옵니다.
- 사양이 좋은 PC에서 더 빠르게: `install.bat -Jobs 3`(3벌 동시 빌드, 1벌당 CPU 4스레드·RAM 6GB 정도).
- DLC 의상은 그 DLC가 설치된 스텔라 블레이드에서만 만들어집니다. DLC가 없으면 그 의상만 건너뛰고 나머지는 설치됩니다.
  한 벌이 실패해도 나머지는 설치되고, 마지막에 `failed outfits`로 알려 줍니다.
- Blender 등 도구는 따로 설치할 필요가 없습니다. 설치기가 이 폴더의 `tools\` 안에 받아서 씁니다(PC에 설치되지 않고, 폴더를 지우면 함께 사라집니다).

**걸리는 시간** (2026-10-21 깨끗한 설치로 측정, 16스레드 CPU + NVIDIA GPU, `-Jobs 3`, GPU가 없으면 더 느림):
| 단계 | 시간 |
|---|---|
| 도구 다운로드 (Blender, .NET, 편집 도구, 약 1GB) | 2.5분 (인터넷 속도에 따라 다름), 처음 한 번만 |
| 두 게임에서 이브 파일 꺼내기 | 1.5분, 처음 한 번만 |
| 이브 얼굴 + 기본 외형 2종 | 4분 |
| 의상 20벌 | `-Jobs 3`으로 19분 (한 벌씩이면 약 45분) |
| **합계** | **27분** |

**의상 목록** (굵은 글씨 = 한국어 게임 이름, 아래 줄 = 영어 게임 이름. 같은 갑옷이 두 줄로 나오면 이브 의상은 ◆ 줄입니다)

| 번호 | 이브 의상 (스텔라 블레이드 이름) | 몬헌에서 입을 갑옷 (한국어 / 영어 게임) | 외형 메뉴 위치 | DLC | 코드 |
|---|---|---|---|---|---|
| 27 | **오션 메이드**<br>Ocean Maid | **옷 타입 4 (옷β ◆)**<br>Outfit type 4 (β ◆) | 차림새 변경 → 헌터 → 옷 타입 | - | `CH_P_EVE_27` |
| 63 | **웨이브 다이버 비키니**<br>Wave Diver Bikini | **옷 타입 3 (옷β ●)**<br>Outfit type 3 (β ●) | 차림새 변경 → 헌터 → 옷 타입 | - | `CH_P_EVE_63` |
| 144 | **플래닛 다이브 슈트(7th)**<br>Planet Diving Suit (7th) | **다하딜라γ**<br>Dahaad γ | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_09` |
| 146 | **워 드레스**<br>War Dress | **앵파α**<br>Sakuratide α<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_59_TypeB` |
| 147 | **엘레강스 드레스**<br>Elegant Dress | **블로섬α**<br>Blossom α<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | NIKKE | `CH_P_EVE_Nikke_02` |
| 148 | **플래닛 다이브 슈트(6th)**<br>Planet Diving Suit (6th) | **아피α**<br>Afi α<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_08` |
| 149 | **블루 몬순**<br>Blue Monsoon | **다이버α**<br>Diver α<br>(몸통과 허리 둘 다 입기, 목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_43` |
| 150 | **요르하 비공식 의례복**<br>YoRHa Unofficial Ceremonial Attire | **고스투라α**<br>Dreamwalker α | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | NieR | `CH_P_EVE_Nier_03` |
| 151 | **모티베이션**<br>Motivation | **하베스트α**<br>Harvest α | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_25` |
| 152 | **사이버 버니**<br>Cyber Bunny | **세레모니얼α**<br>Ceremonial α<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_47` |
| 153 | **산타 드레스**<br>Santa Dress | **오리온α**<br>Orion α | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_Christmas_01` |
| 156 | **오르카 엔지니어**<br>Orca Engineer | **역경 아머α**<br>Bale Armor α | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_15_V02` |
| 157 | **포세컨즈 디스트로이드 데님**<br>FourSeconds Destroyed Denim<br>(재현 데이터 없음: 자동 빌드 그대로, 게임 확인 안 됨) | **오메가 의상α**<br>Omega Attire α<br>(게임 확인 안 됨(자동 빌드)) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_51` |
| 158 | **요르하 제복 1**<br>YoRHa Uniform 1 | **푸른빛무사α**<br>Azure Age α | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | NieR | `CH_P_EVE_Nier_02` |
| 159 | **데일리 포스**<br>Daily Force | **퀸α**<br>Sororal α | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_39` |
| 185 | **레드 패션**<br>Red Passion | **길드나이트**<br>Guild Knight | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_26` |
| 190 | **포세컨즈 에브리데이 웨어**<br>FourSeconds Everyday Wear | **노블레스**<br>Noblesse | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_50_TypeB` |
| 192 | **냉각 슈트**<br>Cooling Suit | **브레이크캣**<br>Cypurrpunk<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | NIKKE | `CH_P_EVE_Nikke_06` |
| 195 | **미싱 링크**<br>Missing Link | **코스모로이드**<br>Cosmoloid | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | NIKKE | `CH_P_EVE_Nikke_05` |
| 9041 | **레이서즈 하이**<br>Racer's High | **미츠네β**<br>Mizutsune β<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_41` |
| 9018 | **데일리 마스코트**<br>Daily Mascot | **레다젤트γ**<br>Rey Dau γ<br>(목록의 ◆ 줄) | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_18` |
| 9034 | **모란**<br>Moutan Peony | **이그졸스γ**<br>Nu Udra γ | 차림새 메뉴 → 헌터 장비 외형 설정 → 몸통 | - | `CH_P_EVE_34_body` |

## 제거
**폴더를 지우기 전에 반드시 먼저 제거하세요.** (폴더를 먼저 지우면 원본 백업도 같이 사라집니다)
1. 몬헌을 끕니다.
2. 시작 메뉴 `Stellar Eve > Stellar Eve 제거`, 또는 `Stellar Eve` 실행 후 **제거 (게임을 원래대로)**, 또는 폴더의 `uninstall.bat` 더블클릭.
3. 확인 창에서 **예**를 누르면 끝납니다. `제거 완료! 게임이 원래대로 돌아왔습니다.`가 나오면 이 폴더를 지워도 됩니다.

제거가 하는 일:
- 이 설치기가 몬헌 폴더에 **새로 넣은 파일을 모두 지우고**(`work\game-backup\added.txt` 목록 기준),
  **덮어썼던 원본은 백업(`work\game-backup\`)에서 되돌립니다.** 비게 된 폴더도 정리합니다.
- 이 폴더를 가리키는 `Stellar Eve` 바탕화면·시작 메뉴 바로가기를 지웁니다.
- 몬헌 **세이브 데이터, REFramework(`dinput8.dll`), 다른 모드는 건드리지 않습니다.**
- 의상 하나만 빼는 기능은 없습니다. 전부 제거한 뒤 원하는 의상만 다시 설치하세요.
- 몬헌 업데이트 후 이상하면: 제거 → Steam에서 "게임 파일 무결성 확인" → 다시 설치.

## 문제 해결
| 메시지 | 할 일 |
|---|---|
| `... is not in your Stellar Blade (DLC not installed?): skipped` | 그 DLC가 없어서 그 의상만 건너뜀. DLC를 설치한 뒤 `install.bat`을 다시 실행하고 그 번호를 고르면 추가됩니다 |
| `Stellar Blade not found` / `Monster Hunter Wilds not found` | 폴더를 직접 지정: `install.bat -SbPaks "...\StellarBlade\SB\Content\Paks" -MhwDir "...\MonsterHunterWilds"` |
| `REFramework is not installed` | 위 "필요한 것"의 REFramework를 넣으세요 |
| `Monster Hunter Wilds is running` | 게임을 끄고 다시 실행 |
| `build failed` | 폴더의 `work\logs\` 로그를 보내 주세요 |

오프라인 전용입니다. 만든 파일(`work\`)이나 설치된 파일을 다른 사람과 공유하지 마세요.

## 보안·개인정보
- **아무 정보도 밖으로 보내지 않습니다.** 인터넷은 `deps.json`에 적힌 도구를 공식 배포처에서 받을 때만 씁니다. 받은 파일은 모두 SHA-256/512로 확인하고, 다르면 멈춥니다. (그 밖에 .NET 도구를 빌드할 때 dotnet이 nuget.org에서 버전이 고정된 패키지를 받습니다.)
- **미리 만든 실행 파일이 없습니다.** `StellarEve.exe`와 두 .NET 도구(`tools\sb-extract`, `tools\motion-convert`)는 이 폴더의 소스로 여러분 PC에서 빌드됩니다.
- 바꾸는 곳: 이 폴더, 몬헌 폴더(넣은 파일은 `work\game-backup\added.txt`에 기록, 덮어쓴 원본은 백업), 바탕화면·시작 메뉴 바로가기(체크했을 때). 레지스트리는 Steam 위치를 **읽기만** 하고, 시작 프로그램·예약 작업·방화벽·백신 설정은 건드리지 않습니다.
- 게임 안 스크립트(`stellar_eve_outfit_bones.lua`)는 REFramework의 `reframework\data\stellar-eve\` 안 JSON 파일만 읽고 씁니다.
- 참고: Stellar Blade 파일을 읽는 CUE4Parse가 SixLabors.ImageSharp 3.1.12를 고정해서 쓰며, 빌드할 때 이 버전의 알려진 취약점 경고가 나옵니다. 여러분 PC의 스텔라 블레이드 텍스처만 읽고 인터넷 이미지는 다루지 않습니다.

## 라이선스
코드: MIT([LICENSE](LICENSE)). 외부 도구: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
스텔라 블레이드와 몬스터 헌터 와일즈의 모든 에셋은 각 권리자(SHIFT UP / Sony Interactive Entertainment, CAPCOM)의 것이며,
이 프로젝트는 비공식으로 그들과 관련이 없습니다.
