import os
import requests
import urllib.parse
import google.generativeai as genai
from datetime import datetime
import pytz
import re

# 1. API 키 및 최신 모델(2026년 기준) 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

# 2026년 현재 가장 안정적인 Gemini 3 및 2 시리즈 모델 리스트입니다.
MODELS_TO_TRY = [
    'gemini-3-flash',        # 최신 고속 모델
    'gemini-3-flash-latest', 
    'gemini-2.0-flash',      # 안정적인 이전 세대 모델
    'gemini-1.5-flash'       # 레거시 모델 (최후의 보루)
]

model = None
chosen_model_name = ""

# 실제로 동작하는 모델을 찾기 위해 간단한 핑(Ping) 테스트를 수행합니다.
for m_name in MODELS_TO_TRY:
    try:
        print(f"모델 체크 중: {m_name}...")
        test_model = genai.GenerativeModel(m_name)
        # 모델이 유효한지 확인하기 위해 아주 짧은 텍스트 생성을 시도합니다.
        test_model.generate_content("test", generation_config={"max_output_tokens": 1})
        model = test_model
        chosen_model_name = m_name
        print(f"✅ 연결 성공: {chosen_model_name}")
        break
    except Exception as e:
        print(f"❌ {m_name} 사용 불가: {e}")
        continue

if not model:
    # 모든 모델이 실패할 경우, HTML에 구체적인 가이드를 남깁니다.
    deal_content = "<div class='deal-card'><h3>🚨 모든 AI 모델을 호출할 수 없습니다.</h3><p>API 키가 만료되었거나 프로젝트 권한 설정을 다시 확인해 주세요.</p></div>"
    # 이 경우 아래 뉴스 수집 단계를 건너뛰고 HTML 생성으로 바로 갈 수 있게 처리
    news_context = "" 

# 2. 네이버 API 뉴스 검색 (로직 동일)
queries = [
    "반도체 M&A", "반도체 인수합병", "바이오 M&A", "바이오 인수합병",
    "배터리 M&A", "이차전지 투자유치", "스타트업 시리즈A B 투자"
]
exclude_keywords = ["설비", "공장", "증설", "채용", "주가", "특징주"]

news_context = ""
idx = 1
seen_titles = set()
headers = {"X-Naver-Client-Id": naver_client_id, "X-Naver-Client-Secret": naver_client_secret}

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).replace('&quot;', '"').replace('&amp;', '&')

for q in queries:
    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=50&sort=sim"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for item in res.json().get('items', []):
                title = clean_html(item['title'])
                link = item['originallink'] or item['link']
                if any(bad in title for bad in exclude_keywords): continue
                if title not in seen_titles and idx <= 60:
                    seen_titles.add(title)
                    news_context += f"[{idx}] 제목: {title}\n링크: {link}\n\n"
                    idx += 1
    except: continue

# 3. AI 분석 및 요약
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

if model and news_context:
    prompt = f"""
    당신은 글로벌 IB의 시니어 M&A 애널리스트입니다. 아래 뉴스 리스트에서 '반도체, 바이오, 배터리, 기타' 섹터의 자본 거래를 정리하세요.
    오늘 날짜는 [{today_badge}]입니다. 오늘 날짜와 일치하는 뉴스는 <h3> 안에 <span class="new-badge">NEW</span>를 붙이세요.
    반드시 HTML <div> 카드 형식으로만 출력하세요.
    
    [데이터]
    {news_context}
    """
    try:
        result = model.generate_content(prompt)
        if result and hasattr(result, 'text'):
            deal_content = result.text.replace('```html', '').replace('```', '').strip()
        else:
            deal_content = "<div class='deal-card'><h3>🎯 분석 결과가 없습니다.</h3></div>"
    except Exception as e:
        deal_content = f"<div class='deal-card'><h3>🎯 AI 요약 에러: {str(e)}</h3></div>"
elif not news_context:
    deal_content = "<div class='deal-card'><h3>🎯 수집된 뉴스가 없습니다.</h3></div>"

# 4. HTML 대시보드 생성 (CSS 동일 유지)
html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>M&A News for ISU OI Team</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; }}
        .container {{ max-width: 900px; margin: auto; }}
        .header-container {{ text-align: center; border-bottom: 2px solid #1a365d; padding-bottom: 15px; margin-bottom: 25px; }}
        .isu-title {{ font-size: 2.3em; color: #1a365d; }}
        .filter-btn {{ background: #e2e8f0; border: none; padding: 10px 20px; border-radius: 20px; cursor: pointer; font-weight: bold; margin: 5px; }}
        .deal-card {{ background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #2b6cb0; }}
        .new-badge {{ background-color: #e53e3e; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; margin-right: 8px; }}
        .source-link {{ color: #dd6b20; font-weight: bold; text-decoration: none; background: #feebc8; padding: 2px 6px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-container">
            <h1 class="isu-title">M&A News for ISU OI Team</h1>
            <p>업데이트: {today_str}</p>
        </div>
        <div id="deal-list">{deal_content}</div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
