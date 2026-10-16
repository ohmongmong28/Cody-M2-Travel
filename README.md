# ✈️️ CLI 기반 국내 여행 계획 자동 추천 프로그램

사용자가 입력한 날짜(`-date`)를 바탕으로 LLM이 최적의 국내 여행지를 추천하고, 카카오 로컬(Kakao Local) API로 현지 맛집 정보를 수집한 뒤, 최종 종합 여행 리포트를 자동 생성하는 파이프라인 CLI 도구입니다.

---

## 1. 프로젝트 파이프라인

```text
[사용자 입력: -date]
       │
       ▼
[1단계: LLM 1차 추천] ───> JSON 생성 (추천 도시 2~3곳, 날씨 요약, 축제/행사, 추천 사유)
       │
       ▼ (도시 목록 루프 순회)
[2단계: Kakao Local API] ──> 각 도시별 맛집 검색 (최대 5건 추출, 좌표/주소 수집)
       │
       ▼ (1차 추천 + 맛집 데이터 결합)
[3단계: LLM 종합 리포트] ──> 최종 여행 리포트 Markdown 생성
       │
       ▼
[4단계: 결과물 자동 저장] ──> results/ 디렉토리에 원본 JSON 및 .md 파일 영구 보관
2. 주요 기능 및 요구사항 충족 현황구분요구사항구현 내용CLIargparse 기반 날짜 입력-date 및 --date 지원, YYYY-MM-DD 정규 형식 검증LLM 연동구조화된 출력 (Structured Output)response_format={"type": "json_object"} 활용 스키마 보장장소 API카카오 로컬 검색 연동키워드 기반 맛집 검색, 최소 필드(name, address, x, y, url) 추출안정성에러 격리 (Fault-Tolerance)맛집 검색 실패(401/403/네트워크) 시에도 리포트 중단 없이 '데이터 없음' 처리재시도LLM JSON 파싱 보정JSON 디코딩 실패 시 프롬프트 보정 후 최대 1회 재시도 (무한 루프 방지)보안API 키 분리 관리.env 및 python-dotenv 사용, 코드 및 저장소 내 키 노출 원천 차단결과 저장파일 생성 및 아카이빙results/ 폴더 내 원본 JSON (errors 포함) 및 Markdown 파일 저장3. 보너스 과제 구현 (Bonus Tasks)① 복수 지역 추천 (Multiple Cities)1차 추천 단계를 단일 도시가 아닌 2~3개 도시 배열(recommended_cities)로 확장 설계하였습니다.파이썬 for 루프를 통해 각 도시마다 카카오 로컬 API를 개별 호출하고 결과를 그룹화합니다.최종 리포트 및 원본 JSON에 지역별 일정과 맛집이 구조적으로 정리되어 출력됩니다.② 결과 캐싱 (Result Caching)동일한 날짜(-date)로 프로그램을 다시 실행할 경우, results/ 폴더 내 기존 파일({date}_data.json, {date}_report.md)을 탐색합니다.이미 생성된 데이터가 존재하면 외부 API(OpenAI, Kakao) 호출을 전면 생략하고 캐시된 결과를 즉시 안내하여 API 비용을 절감하고 응답 속도를 극대화했습니다.4. 개발 환경 및 설치 방법개발 환경Python 3.10 이상OS: Windows, macOS, Linux 지원가상환경 세팅 및 라이브러리 설치Bash# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
.\venv\Scripts\activate
# 가상환경 활성화 (macOS / Linux)
# source venv/bin/activate

# 필수 라이브러리 설치
pip install requests python-dotenv openai
5. API 키 설정 및 보안 가이드프로젝트 루트 경로에 .env 파일을 생성하고 아래 형식으로 키를 설정합니다.코드 스니펫OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=your_base_url_here  # 코디세이 등 프록시 엔드포인트 사용 시 기재 (선택)
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
보안 관리 원칙코드 내 키 하드코딩 금지: .env 파일과 os.getenv()를 통해 런타임에 주입받습니다.저장소 유출 방지: .gitignore에 .env와 venv/를 반드시 등록하여 GitHub 커밋 시 키가 업로드되는 사고를 방지합니다.사전 검증: 프로그램 시작 시 필수 키 등록 여부를 검사하여 누락 시 설정 안내와 함께 즉시 안전 종료합니다.6. 프로그램 실행 방법기본 실행 (정상 케이스)Bashpython travel_planner.py -date "2026-05-15"
실행 화면 예시Plaintext🚀 여행 계획 생성 시작 (입력 날짜: 2026-05-15)
[1/3] 1차 복수 추천 지역 생성 중 (LLM)...
  └ 추천된 도시 목록: ['강릉', '제주', '부산']
[2/3] 추천된 각 도시별 맛집 검색 중 (Kakao Local API)...
  - '강릉' 맛집 검색 요청...
    └ 5곳 확보 완료
  - '제주' 맛집 검색 요청...
    └ 5곳 확보 완료
  - '부산' 맛집 검색 요청...
    └ 5곳 확보 완료
[3/3] 지역별 정보를 결합하여 최종 리포트 생성 중 (LLM)...
  └ 리포트 생성 완료

🎉 모든 작업이 완료되었습니다!
  - 원본 JSON 데이터: results\2026-05-15_data.json
  - 최종 여행 리포트: results\2026-05-15_report.md
캐시 동작 확인 (동일 날짜 재실행)Bashpython travel_planner.py -date "2026-05-15"

# 출력:
⚡ [캐시 발견] '2026-05-15' 날짜의 결과가 이미 존재합니다!
👉 외부 API 호출을 모두 건너뛰고 기존 저장된 데이터를 재사용합니다 (비용/시간 절약).
  - 원본 JSON: results\2026-05-15_data.json
  - 여행 리포트: results\2026-05-15_report.md
입력 검증 실패 케이스Bashpython travel_planner.py -date "2026-99-99"

# 출력:
[입력 오류] 날짜 형식은 반드시 'YYYY-MM-DD' 형태여야 합니다: 2026-99-99
사용 예시: python travel_planner.py -date '2026-05-15'
7. 결과물 확인 안내실행 완료 후 results/ 폴더 내에 2개 파일이 생성됩니다.1) 원본 데이터 (results/YYYY-MM-DD_data.json)LLM 1차 추천 결과와 카카오 API 수집 데이터, 런타임 오류 추적 목록이 포함됩니다.JSON{
  "travel_date": "2026-05-15",
  "recommendations": [
    {
      "city": "강릉",
      "weather": "맑고 선선한 바닷바람",
      "events": ["단오제 관련 행사"],
      "reason": "바다를 보며 힐링하기 최적의 시기입니다."
    }
  ],
  "places_by_city": {
    "강릉": [
      {
        "name": "초당순두부마을 맛집",
        "address": "강원 강릉시 초당동",
        "category": "음식점 > 한식",
        "url": "[http://place.map.kakao.com/](http://place.map.kakao.com/)...",
        "x": 128.91,
        "y": 37.79
      }
    ]
  },
  "errors": []
}
2) 최종 여행 리포트 (results/YYYY-MM-DD_report.md)추천 이유, 날씨, 행사, 맛집, 1일 추천 코스가 서식화된 마크다운 문서입니다.8. 학습 목표 자가 진단 및 개념 정리Q1. REST API의 요청/응답 구조와 HTTP 메서드(GET/POST)의 차이GET: 쿼리스트링(URL 파라미터)을 통해 서버에 데이터를 요청하며, 주로 조회/검색에 사용됩니다. (본 프로젝트의 카카오 로컬 맛집 검색 API)POST: 요청 본문(Body)에 데이터를 실어 전송하며, 주로 새로운 리소스 생성 및 서버 처리 요청에 사용됩니다. (본 프로젝트의 LLM 프롬프트 전달 및 텍스트 생성 API)Q2. LLM 출력 결과를 구조화(JSON)하여 다음 단계의 입력으로 연결하는 이유자연어 텍스트는 매 호출마다 문장 구조가 달라 파이썬 코드가 특정 값(도시 이름 등)만 골라내기 어렵습니다.JSON 포맷으로 강제 출력(Structured Output)하면 파이썬의 딕셔너리로 바로 역직렬화(json.loads)할 수 있어, 추출한 도시명을 다음 단계(지도 API)의 동적 매개변수로 안전하게 전달할 수 있습니다.Q3. 외부 API 호출 오류(인증/쿼터/네트워크/파싱)와 대응 원칙예외 격리(Graceful Degradation): 장소 검색 API에서 인증(401/403)이나 쿼터 초과 등의 오류가 발생하더라도 전체 프로그램을 다운시키지 않고, 맛집 섹션을 '데이터 없음' 처리한 뒤 오류 로그(errors)를 남겨 최종 리포트까지 파이프라인이 완주하도록 설계했습니다.재시도 제한: LLM 파싱 오류 시 프롬프트를 보정하여 1회만 재시도함으로써 무한 루프로 인한 불필요한 과금을 방지합니다.Q4. API 키를 환경변수(.env)로 관리하는 이유보안성: GitHub 등 버전 관리 시스템에 키가 평문으로 노출되어 발생하는 무단 과금 및 계정 도용 사고를 방지합니다.유지보수성: 운영 환경이나 키가 변경될 때 소스 코드를 수정하거나 다시 빌드할 필요 없이 설정 파일만 교체하여 유연하게 대응할 수 있습니다.