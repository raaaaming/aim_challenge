# 포항항 ⚓ — 대화로 찾는 나의 포항 여행지

LLM과 대화하며 취향을 파악하고, `여행지_20_포항.csv` 의 20곳 중 **딱 한 곳**을 추천하는 대화형 웹 서비스.

## 기술 스택 (기술 스택.txt 준수)

| 레이어 | 사용 기술 |
|---|---|
| Frontend | **React (Vite)** + **Tailwind CSS** |
| Backend | **Python / FastAPI** |
| DB & Storage | **Supabase** — FastAPI 백엔드의 `backend/app/supabase.py` 를 통해서만 연동 |
| LLM | **무료 등급만 사용** — Google Gemini(AI Studio 무료) / Groq / OpenRouter `:free`. 키가 없으면 내장 규칙 엔진으로 자동 동작 |

## 디렉터리

```
├── 여행지_20_포항.csv / 평가 기준.txt / 기술 스택.txt   원본 입력
├── data/
│   ├── places.json          여행지 20곳 + 200개 점수 + 근거 (앱 마스터 데이터)
│   ├── place_scores.csv     점수만 뽑은 표
│   └── places_utf8.csv      원본 CSV 의 UTF-8 변환본
├── docs/평가근거.md          ★ 200개 점수 각각의 산정 근거 문서
├── tools/
│   ├── scores_data.py       평가 축 정의 + 20×10 점수·근거 원장
│   └── build_scores.py      data/ · docs/ · supabase/seed_data.json 생성기
├── supabase/
│   ├── schema.sql           테이블·RLS·Storage 버킷 DDL
│   ├── seed_data.json       적재용 payload
│   └── seed.py              시딩 + 이미지 업로드 스크립트
├── backend/
│   ├── app/supabase.py      ← Supabase 연동 지점 (요구사항)
│   ├── app/tournament.py    2택 월드컵(Elo·반응시간) 추천 엔진 (self-check: python -m app.tournament)
│   ├── app/recommender.py   취향 벡터 → 가중 거리 fit_score
│   ├── app/describe.py      결과 설명 재생성 (CSV 7개 필드만 사용)
│   └── app/llm.py           무료 LLM 어댑터
└── frontend/src/screens/    SplashScreen · MatchScreen · ResultScreen
```

## 실행

### 1) 백엔드

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # LLM_API_KEY, SUPABASE_* 채우기 (없어도 실행됨)
uvicorn app.main:app --reload --port 8000
```

`GET /api/health` 로 데이터 소스(`supabase`/`local`), LLM 상태를 확인할 수 있습니다.

### 2) 프론트엔드

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (/api 는 8000 으로 프록시)
```

### 3) Supabase 연결 (선택 → 권장)

```bash
# ① 대시보드 SQL Editor 에 supabase/schema.sql 붙여넣고 실행
# ② backend/.env 에 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 입력
# ③ 시딩
python3 supabase/seed.py                 # places(20) + preference_axes(10)
python3 supabase/seed.py --images        # assets/images/pohang_0XX.jpg → Storage
```

이미지는 `assets/images/pohang_001.jpg` … `pohang_020.jpg` 이름으로 두면
`place-images` 버킷에 올라가고, 최종 결과 화면이 해당 public URL 을 사용합니다.
(버킷에 이미지가 없으면 결과 화면은 그라디언트 폴백을 표시합니다.)

### 4) LLM 무료 키

| provider | 발급처 | 기본 모델 |
|---|---|---|
| `gemini` (기본) | https://aistudio.google.com/apikey | `gemini-2.0-flash` |
| `groq` | https://console.groq.com/keys | `llama-3.3-70b-versatile` |
| `openrouter` | https://openrouter.ai/keys | `...-instruct:free` |

`LLM_PROVIDER=rule` 로 두면 키 없이 내장 규칙 엔진으로 동일한 대화 흐름이 돌아갑니다.

## 평가 축 10개

`평가 기준.txt` 의 취향 지표를 각각 **0.0 ~ 10.0 단일 연속 축**으로 정의했습니다.

| # | 지표 | 우선순위 | 0.0 | 10.0 |
|---|---|:--:|---|---|
| 1 | 선호 이동 수단/출발 위치 | P1 | 자차 필요 외곽 | 도심·대중교통 |
| 2 | 전시·관람형 / 참여형 | P0 | 관람형 | 참여·체험형 |
| 3 | 자연 경관 / 미식 | P0 | 자연 경관 | 미식 |
| 4 | 누구와 함께 | P1 | 혼자·둘이 | 가족·단체 |
| 5 | 교통 약자/도보 선호도 | P0 | 보행 부담 큼 | 평지·무장애 |
| 6 | 한적 / 활기찬 핫플 | P0 | 한적 | 핫플 |
| 7 | 가벼운 여행 / 역사·문화 탐방 | P0 | 가벼움 | 탐방 |
| 8 | 야외 / 실내 | P0 | 야외 | 실내 |
| 9 | 예산 범위 | P0 | 무료 | 고비용 |
| 10 | 체류 시간 | P0 | 짧게 | 반나절+ |

추천식:
```
w_k       = 우선순위가중치(P0=1.0, P1=0.6) × 사용자 확신도 c_k
distance  = Σ w_k·|여행지점수_k − 사용자값_k| / Σ w_k
fit_score = (1 − distance/10) × 100
```

## 화면 흐름

1. **첫 시작 화면** — 중앙보다 약간 위(-8vh)에 **포항항** 로고, 1.6초 가짜 로딩(물결 애니메이션) 후 **바로 월드컵 화면**으로 전환
2. **2택 월드컵 화면** — 두 여행지 카드(무엇을 할 수 있는지·누구에게 맞는지) 중 **더 끌리는 곳**을 탭. 총 12라운드, 상단에 진행률 표시
   - 빠르게 고를수록(= 더 끌릴수록) 그 선택의 가중치(Elo K)가 커짐
   - 12라운드 뒤 Elo 레이팅으로 전체 순위 산출 → **1위**를 결과로
   - 고른 곳들의 10축 점수를 반응시간 가중 평균해 **사용자 취향 벡터**를 역산
3. **최종 결과 화면** (1위)
   - CSV 의 `place_name` 원문 그대로 노출
   - 설명은 `summary` / `embedding_text` / `evidence_text_1~5` **7개 필드만으로 재생성**
   - Supabase Storage 의 여행지 이미지 삽입
   - 10축 점수 막대(여행지 · 내 응답) + "이래서 골랐어요"(취향 벡터 근거) + 재생성 원문 펼쳐보기

## 데이터 재생성

```bash
python3 tools/build_scores.py
```
