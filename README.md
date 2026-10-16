# ✈️️ CLI 기반 국내 여행 계획 자동 추천 시스템

사용자가 입력한 특정 날짜(`-date`)를 바탕으로 LLM API(OpenAI)와 장소 검색 API(Kakao Local)를 유기적으로 결합하여, 지역 추천부터 맛집 수집, 일정 구성까지 완결된 여행 리포트를 자동 생성하는 데이터 파이프라인 CLI 프로그램입니다.

---

## 📌 1. 프로젝트 핵심 요약 (1분 브리핑)

> 본 프로젝트는 **"단일 API 호출을 넘어 서로 다른 성격의 API를 엮어 유의미한 비즈니스 인사이트를 도출하는 데이터 조립 파이프라인"**을 구축하는 데 집중했습니다.
> 1. **입력 검증**: 사용자가 입력한 날짜의 유효성을 검사합니다.
> 2. **1차 추천 (LLM)**: 날짜 정보를 기반으로 방문하기 좋은 국내 도시 2~3곳과 날씨, 행사 정보를 **정형화된 JSON**으로 추출합니다.
> 3. **맛집 연동 (Kakao Local)**: 추출된 도시명을 파이썬 루프(`for`)로 순회하며 카카오 로컬 API(GET)를 호출해 도시별 맛집 5곳의 메타데이터를 수집합니다.
> 4. **종합 리포트 생성 (LLM)**: 취합된 데이터와 런타임 에러 로그를 종합하여 Markdown 포맷의 최종 리포트를 작성하고 영구 보관합니다.
> 5. **최적화 & 안정성**: 중복 실행 시 API 비용과 응답 지연을 방지하는 **결과 캐싱(Caching)**과, 외부 API 실패 시에도 파이프라인이 중단되지 않는 **예외 격리(Graceful Degradation)**를 구현했습니다.
> 
> 

---

## 🏗️ 2. 데이터 파이프라인 구조

```text
[사용자 입력]  python travel_planner.py -date "YYYY-MM-DD"
     │
     ├─▶ [캐시 확인] 이미 생성된 {date}_data.json 존재 시 ───▶ API 호출 생략 후 캐시 즉시 반환 (0.1초)
     │
     ▼ (미존재 시)
[Step 1. LLM 1차 추천 (POST)]
     │  - System Prompt로 JSON Schema 엄격 강제
     │  - 출력: { "recommended_cities": [{ "city": "강릉", ... }, ...] }
     │
     ▼ (도시명 추출 후 파이썬 Loop 순회)
[Step 2. Kakao Local API (GET)]
     │  - query="{city} 맛집", size=5
     │  - 장애 격리: 401/403/네트워크 오류 발생 시 '빈 리스트' 처리 및 error_logs 적재
     │
     ▼ (1차 추천 JSON + 맛집 리스트 병합)
[Step 3. LLM 리포트 생성 (POST)]
     │  - 마크다운 규격 문서 자동 생성 (추천 사유, 날씨, 축제, 맛집, 1일 코스)
     │
     ▼
[Step 4. 결과 영구 보관]
     ├─▶ results/{date}_data.json (원본 메타데이터 + 에러 추적 로그)
     └─▶ results/{date}_report.md (최종 여행 계획서 마크다운)

```

---

## 💡 3. 핵심 기술 설계 및 질의응답 (Architecture Q&A)

평가 시 확인하는 핵심 개념 4가지와 구현 의도입니다.

### Q1. REST API의 GET과 POST 메서드 차이 및 코드 적용 사례

* **GET (조회/수집)**:
* 요청 데이터가 URL 쿼리 파라미터(`?query=강릉 맛집&size=5`)에 노출되며, 서버의 상태를 변경하지 않는 멱등성(Idempotent)을 가집니다.
* **코드 적용**: `step2_search_places()`에서 카카오 로컬 API를 통해 장소 목록을 **단순 조회**할 때 `requests.get()`을 사용했습니다.


* **POST (생성/처리)**:
* 대용량 데이터나 프롬프트 본문(Body)을 감싸서 전송하며, 서버에 새로운 처리나 연산을 위임합니다.
* **코드 적용**: `step1_llm_recommend_multiple()` 및 `step3_generate_report()`에서 시스템 프롬프트와 페이로드를 OpenAI 서버로 전송해 **새로운 텍스트/JSON을 생성**할 때 `client.chat.completions.create()`(POST)를 사용했습니다.



### Q2. LLM 출력을 비정형 텍스트 대신 정형 JSON으로 구조화한 이유

* LLM이 줄글 형태로 답변하면 매 실행마다 문장 구조나 단어가 바뀌기 때문에, 파이썬 코드가 정규표현식이나 문자열 슬라이싱으로 특정 도시명만 안전하게 발라내기 불가능합니다.
* LLM의 `response_format={"type": "json_object"}` 옵션과 명확한 JSON 스키마를 지정해 응답을 **JSON 객체로 강제**함으로써, 파이썬이 `item["city"]`처럼 키 기반으로 안전하게 파싱하여 다음 파이프라인 단계(카카오 API 호출 매개변수)의 입력값으로 직결할 수 있도록 설계했습니다.

### Q3. 외부 API 호출 오류(인증/네트워크/쿼터) 대응 원칙

* **예외 격리 (Graceful Degradation)**:
* 지도 API에서 인증 실패(401/403), 일일 쿼터 초과, 타임아웃이 발생하거나 검색 결과가 0건이어도 프로그램 전체가 비정상 종료(`Crash`)되지 않습니다.
* 오류 발생 시 맛집 섹션을 `"데이터 없음 (장소 검색 결과 0건)"` 상태로 격리하고, 오류 내역은 `error_logs` 리스트에 수집한 뒤 최종 리포트 생성 단계까지 파이프라인 완주를 보장합니다.


* **재시도 제한 (Retry-Limit)**:
* LLM 응답 JSON 파싱 실패 시, 무한 루프로 인한 요금 폭탄을 방지하기 위해 프롬프트를 1회 보정한 뒤 최대 1회만 재시도하도록 안전장치를 두었습니다.



### Q4. API 키를 코드에 직접 적지 않고 `.env`로 격리하는 이유

* **보안 사고 예방**: GitHub 등 공개 레포지토리에 코드가 업로드될 때 하드코딩된 API 키가 외부로 유출되어 발생하는 무단 과금 및 계정 도용 사고를 원천 차단합니다. (`.gitignore`로 `.env` 추적 배제)
* **환경 분리 및 유지보수**: 개발 환경, 테스트 환경, 운영 환경에 따라 코드를 수정하지 않고 `.env` 파일의 설정값만 교체하여 유연하게 프로그램을 실행할 수 있습니다.

---

## 🌟 4. 보너스 과제 구현 (Bonus Tasks)

### 1) 복수 지역 추천 및 반복 처리 (Loop Handling)

* 1차 추천 단계를 단일 지역에서 2~3개 추천 도시 배열(`recommended_cities`)로 확장 설계했습니다.
* 파이썬 `for city in cities:` 루프를 통해 각 지역별로 카카오 맛집 검색 API를 개별 호출하고, 결과를 `{ "도시명": [맛집목록] }` 딕셔너리로 그룹화하여 최종 리포트에 지역별 섹션으로 정리해 제공합니다.

### 2) 결과 캐싱 (Result Caching)

* 프로그램 실행 시 인자로 들어온 날짜를 기준으로 `results/{date}_data.json` 파일의 존재 여부를 가장 먼저 확인합니다.
* 이미 처리된 이력이 있다면 OpenAI 및 Kakao API 호출을 **전면 건너뛰고(Bypass)** 기존 저장된 결과를 화면에 안내합니다.
* **효과**: 반복 실행 시 외부 API 호출 비용을 0원으로 줄이고, 응답 속도를 수 초에서 **0.1초 이내**로 최적화했습니다.

---

## 🚀 5. 실행 환경 및 사용 방법

### 1) 설치

```bash
# 가상환경 생성 및 활성화 (Windows)
python -m venv venv
.\venv\Scripts\activate

# 필수 패키지 설치
pip install requests python-dotenv openai

```

### 2) 환경변수 설정 (`.env`)

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 키를 설정합니다.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=your_proxy_url_here  # 코디세이 프록시 등 엔드포인트가 별도로 존재할 경우 기재
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here

```

### 3) 실행 명령어

```bash
# 기본 실행 (YYYY-MM-DD)
python travel_planner.py -date "2026-05-15"

# 캐시 검증: 동일 날짜로 재실행 시 캐시 안내 출력
python travel_planner.py -date "2026-05-15"

# 입력 검증 테스트: 잘못된 날짜 형식 입력 시 즉시 사용법 출력 후 종료
python travel_planner.py -date "2026-99-99"

```

---

## 📂 6. 산출물 구조 및 데이터 규격

프로그램 실행 완료 시 `results/` 폴더에 아래 2가지 포맷으로 결과가 자동 아카이빙됩니다.

### 1) 원본 데이터 (`results/YYYY-MM-DD_data.json`)

파이프라인 단계별 원시 데이터와 오류 추적 로그를 포함합니다.

```json
{
  "travel_date": "2026-05-15",
  "recommendations": [
    {
      "city": "강릉",
      "weather": "맑고 온화하며 바닷바람이 상쾌함",
      "events": ["단오제 관련 행사", "커피 거리 축제"],
      "reason": "봄바다를 감상하며 힐링하기에 최적화된 시기입니다."
    }
  ],
  "places_by_city": {
    "강릉": [
      {
        "name": "초당순두부 본점",
        "address": "강원 강릉시 초당순두부길",
        "category": "음식점 > 한식 > 두부전문점",
        "url": "http://place.map.kakao.com/...",
        "x": 128.9142,
        "y": 37.7912
      }
    ]
  },
  "errors": []
}
