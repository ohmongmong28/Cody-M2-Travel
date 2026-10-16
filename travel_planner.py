import os
import sys
import json
import argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
from openai import OpenAI

# 1. .env 파일 경로 지정 및 환경변수 불러오기
current_dir = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(current_dir, ".env")
load_dotenv(dotenv_path=env_file_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

# 오류 추적을 위한 전역 리스트
error_logs = []

def check_api_keys():
    """API 키 설정 여부 검증 (미설정 시 즉시 종료)"""
    missing_keys = []
    if not OPENAI_API_KEY:
        missing_keys.append("OPENAI_API_KEY")
    if not KAKAO_REST_API_KEY:
        missing_keys.append("KAKAO_REST_API_KEY")
    
    if missing_keys:
        print("[오류] 필수 API 키가 설정되지 않았습니다:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\n.env 파일에 API 키를 올바르게 작성했는지 확인해주세요.")
        sys.exit(1)

def validate_date(date_str):
    """날짜 형식 검증 (YYYY-MM-DD)"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print(f"[입력 오류] 날짜 형식은 반드시 'YYYY-MM-DD' 형태여야 합니다: {date_str}")
        print("사용 예시: python travel_planner.py -date '2026-05-15'")
        sys.exit(1)

def step1_llm_recommend_multiple(client, travel_date):
    """[보너스 1] LLM을 통해 2~3개 복수 추천 지역 및 정보 JSON 생성"""
    system_prompt = """
당신은 한국 국내 여행 전문가입니다.
사용자가 입력한 날짜를 바탕으로 여행하기 좋은 국내 도시 2~3곳을 추천하세요.
반드시 아래 JSON 스키마 규격으로만 응답해야 하며, 마크다운 따옴표(```json) 없이 순수 JSON만 출력하세요.

{
  "recommended_cities": [
    {
      "city": "도시명 (예: 강릉, 부산 등)",
      "weather": "해당 시기 일반적 날씨 요약 1문장",
      "events": ["행사나 축제 또는 주요 즐길거리 1~3개"],
      "reason": "추천 근거 2~3문장"
    }
  ]
}
"""
    user_prompt = f"여행 예정 날짜는 {travel_date} 입니다. 해당 시기에 방문하기 좋은 여행지 2~3곳을 추천해주세요."

    # JSON 파싱 실패 시 1회 재시도 (요구사항)
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            raw_text = response.choices[0].message.content
            parsed_json = json.loads(raw_text)
            
            if "recommended_cities" in parsed_json and len(parsed_json["recommended_cities"]) > 0:
                return parsed_json
            raise ValueError("recommended_cities 키가 누락되었거나 비어있습니다.")
        except Exception as e:
            if attempt == 0:
                user_prompt += " (주의: 이전 출력이 올바른 JSON이 아니었습니다. 반드시 규격에 맞는 JSON만 출력하세요.)"
            else:
                error_logs.append({
                    "step": "llm_recommend",
                    "type": "PARSE_ERROR",
                    "message": f"1차 복수 추천 JSON 파싱 실패: {str(e)}"
                })
                # 기본 대체 데이터
                return {
                    "recommended_cities": [
                        {
                            "city": "제주",
                            "weather": "온화한 날씨",
                            "events": ["자연 경관 탐방"],
                            "reason": "기본 추천지로 대체되었습니다."
                        }
                    ]
                }

def step2_search_places(city_name):
    """카카오 로컬 API로 특정 도시의 맛집 검색 (단일 도시)"""
    url = "[https://dapi.kakao.com/v2/local/search/keyword.json](https://dapi.kakao.com/v2/local/search/keyword.json)"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "query": f"{city_name} 맛집",
        "size": 5
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code in [401, 403]:
            error_logs.append({
                "step": "place_search",
                "city": city_name,
                "type": "AUTH_ERROR",
                "message": f"카카오 API 인증 실패 (HTTP {res.status_code})"
            })
            return []
        
        res.raise_for_status()
        data = res.json()
        documents = data.get("documents", [])

        if not documents:
            error_logs.append({
                "step": "place_search",
                "city": city_name,
                "type": "EMPTY_RESULT",
                "message": f"검색 결과 0건 for query='{city_name} 맛집'"
            })
            return []

        places = []
        for doc in documents:
            places.append({
                "name": doc.get("place_name", "이름 없음"),
                "address": doc.get("road_address_name") or doc.get("address_name", "주소 없음"),
                "category": doc.get("category_name", ""),
                "url": doc.get("place_url", ""),
                "x": float(doc.get("x", 0)),
                "y": float(doc.get("y", 0))
            })
        return places

    except Exception as e:
        error_logs.append({
            "step": "place_search",
            "city": city_name,
            "type": "NETWORK_OR_API_ERROR",
            "message": str(e)
        })
        return []

def step3_generate_report(client, travel_date, plan_data, places_by_city):
    """[보너스 1] 복수 지역 데이터를 지역별로 정리하여 Markdown 리포트 생성"""
    system_prompt = """
당신은 여행 리포트 작성가입니다. 제공된 복수 지역 추천 데이터와 각 지역별 맛집 정보를 종합하여 마크다운 리포트를 작성하세요.
반드시 아래 형식을 지켜주세요:
# [날짜] 국내 여행 추천 리포트 (복수 지역)
## 추천 지역 1: [도시명]
- 날씨 요약:
- 행사 및 축제:
- 추천 이유:
- 맛집 리스트 (맛집이 없으면 "데이터 없음 (장소 검색 결과 0건)"으로 표기):
- 1일 일정 제안 (오전/오후/저녁):

## 추천 지역 2: [도시명]
... (지역별로 동일 구조 반복)

## 시스템 오류 요약 (errors)
(발생한 에러가 있으면 기재, 없으면 "특이사항 없음")
"""
    prompt_content = f"""
여행 날짜: {travel_date}
1차 추천 데이터: {json.dumps(plan_data, ensure_ascii=False)}
지역별 맛집 데이터: {json.dumps(places_by_city, ensure_ascii=False)}
시스템 오류 기록: {json.dumps(error_logs, ensure_ascii=False)}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        error_logs.append({
            "step": "generate_report",
            "type": "LLM_REPORT_ERROR",
            "message": str(e)
        })
        return f"# {travel_date} 리포트 생성 중 오류 발생\n\n내용: {str(e)}"

def save_outputs(travel_date, plan_data, places_by_city, report_md):
    """결과 저장"""
    os.makedirs("results", exist_ok=True)
    
    raw_output = {
        "travel_date": travel_date,
        "recommendations": plan_data.get("recommended_cities", []),
        "places_by_city": places_by_city,
        "errors": error_logs
    }
    json_path = os.path.join("results", f"{travel_date}_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_output, f, ensure_ascii=False, indent=2)

    md_path = os.path.join("results", f"{travel_date}_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return json_path, md_path

def main():
    parser = argparse.ArgumentParser(description="날짜 기반 국내 여행 추천 및 맛집 탐색 프로그램 (보너스 과제 포함)")
    parser.add_argument("-date", "--date", required=True, help="여행 날짜 (형식: YYYY-MM-DD)")
    args = parser.parse_args()

    travel_date = validate_date(args.date)
    
    # ----------------------------------------------------
    # [보너스 2: 결과 캐싱 검사]
    # ----------------------------------------------------
    json_path = os.path.join("results", f"{travel_date}_data.json")
    md_path = os.path.join("results", f"{travel_date}_report.md")

    if os.path.exists(json_path) and os.path.exists(md_path):
        print(f"\n⚡ [캐시 발견] '{travel_date}' 날짜의 결과가 이미 존재합니다!")
        print(f"👉 외부 API 호출을 모두 건너뛰고 기존 저장된 데이터를 재사용합니다 (비용/시간 절약).")
        print(f"  - 원본 JSON: {json_path}")
        print(f"  - 여행 리포트: {md_path}")
        print("💡 새로 API를 호출해 갱신하고 싶다면 results 폴더의 해당 파일을 삭제하고 실행하세요.\n")
        return

    # 캐시가 없는 경우 API 호출 진행
    check_api_keys()

    if OPENAI_BASE_URL:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    else:
        client = OpenAI(api_key=OPENAI_API_KEY)

    print(f"\n🚀 여행 계획 생성 시작 (입력 날짜: {travel_date})")

    # 1. 복수 지역 추천 (LLM)
    print("[1/3] 1차 복수 추천 지역 생성 중 (LLM)...")
    plan_data = step1_llm_recommend_multiple(client, travel_date)
    cities = [item.get("city") for item in plan_data.get("recommended_cities", [])]
    print(f"  └ 추천된 도시 목록: {cities}")

    # 2. 각 도시별 맛집 검색 루프 (Kakao API 반복 호출)
    print(f"[2/3] 추천된 각 도시별 맛집 검색 중 (Kakao Local API)...")
    places_by_city = {}
    for city in cities:
        print(f"  - '{city}' 맛집 검색 요청...")
        places = step2_search_places(city)
        places_by_city[city] = places
        print(f"    └ {len(places)}곳 확보 완료")

    # 3. 종합 리포트 생성 (LLM)
    print("[3/3] 지역별 정보를 결합하여 최종 리포트 생성 중 (LLM)...")
    report_md = step3_generate_report(client, travel_date, plan_data, places_by_city)
    print("  └ 리포트 생성 완료")

    # 저장
    json_file, md_file = save_outputs(travel_date, plan_data, places_by_city, report_md)
    print(f"\n🎉 모든 작업이 완료되었습니다!")
    print(f"  - 원본 JSON 데이터: {json_file}")
    print(f"  - 최종 여행 리포트: {md_file}\n")

if __name__ == "__main__":
    main()