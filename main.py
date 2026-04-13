import os
import requests
import json
import urllib.parse
from datetime import datetime
import pytz
import re
import time

# 1. 환경 변수 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
NAVER_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

# 2. 네이버 뉴스 수집 로직
queries = ["반도체 M&A", "바이오 인수합병", "배터리 투자유치", "스타트업 시리즈A"]
exclude_keywords = ["설비", "공장", "채용", "주가"]
news_context = ""
idx = 1
seen_titles = set()
headers_naver = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}

def clean_html(raw_html):
    return re.sub('<.*?>', '', raw_html).replace('&quot;', '"').replace('&amp;', '&')

for q in queries:
    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=30&sort=sim"
    try:
        res = requests.get(url, headers=headers_naver, timeout=10)
        if res.status_code == 200:
            for item in res.json().get('items', []):
                title = clean_html(item['title'])
                link = item['originallink'] or item['link']
                if any(bad in title for bad in exclude_keywords): continue
                if title not in seen_titles and idx <= 40:
                    seen_titles.add(title)
                    news_context += f"[{idx}] {title}\n"
                    idx += 1
    except: continue

# 3. Gemini API 호출 (v1beta 경로 사용 및 에러 제어)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 2026년 무료 티어에서 가장 응답이 빠른 모델 순서입니다.
MODELS_TO_TRY = ["gemini-1.5-flash", "gemini-1.5-pro"]
deal_content = ""

prompt = f"당신은 IB 애널리스트입니다. 아래 뉴스에서 M&A 및 투자 관련 내용을 섹터별로 요약하세요. HTML <div> 카드 형식으로만 출력하고 사족은 생략하세요. 오늘날짜: {today_badge}\n\n뉴스:\n{news_context}"

for model_id in MODELS_TO_TRY:
    # 404 에러 방지를 위해 v1beta 경로를 사용합니다.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            deal_content = res_json['candidates'][0]['content']['parts'][0]['text']
            deal_content = deal_content.replace('```html', '').replace('```', '').strip()
            break
        elif response.status_code == 429:
            print(f"⚠️ {model_id}가 너무 바쁩니다. 잠시 대기합니다.")
            time.sleep(5) # 429 에러 시 5초 대기 후 다음 모델 시도
        else:
            print(f"❌ {model_id} 호출 실패 (코드 {response.status_code})")
    except: continue

if not deal_content:
    deal_content = "<div class='deal-card'><h3>🚨 서버 과부하 안내</h3><p>구글 API 호출 한도가 일시적으로 초과되었습니다. 10분 뒤에 자동으로 다시 시도됩니다.</p></div>"

# 4. HTML 대시보드 생성
html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>M&A News for ISU OI Team</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; color: #2d3748; }}
        .container {{ max-width: 900px; margin: auto; }}
        .header {{ text-align: center; border-bottom: 2px solid #1a365d; padding-bottom: 15px; margin-bottom: 25px; }}
        .deal-card {{ background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #2b6cb0; }}
        .new-badge {{ background: #e53e3e; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="color:#1a365d;">M&A News for ISU OI Team</h1>
            <p><strong>업데이트: {today_str}</strong></p>
        </div>
        <div id="deal-list">{deal_content}</div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
