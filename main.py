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

# 3. Gemini API 호출 (최적화된 경로와 모델명)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 429 에러를 피하기 위해 가장 가벼운 모델 하나만 집중 공략합니다.
target_model = "gemini-1.5-flash-latest" 
deal_content = ""

prompt = f"당신은 IB 애널리스트입니다. 아래 뉴스에서 M&A 및 투자 관련 내용을 섹터별로 요약하세요. HTML <div> 카드 형식으로만 출력하고 사족은 생략하세요. 오늘날짜: {today_badge}\n\n뉴스:\n{news_context}"

# v1beta 경로로 접속합니다.
url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={GEMINI_API_KEY}"
payload = {"contents": [{"parts": [{"text": prompt}]}]}

try:
    # 구글 서버에 '똑똑' 노크하기 전 3초만 쉽니다. (429 방지)
    time.sleep(3)
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        res_json = response.json()
        deal_content = res_json['candidates'][0]['content']['parts'][0]['text']
        deal_content = deal_content.replace('```html', '').replace('```', '').strip()
    elif response.status_code == 429:
        deal_content = "<div class='deal-card'><h3>🚨 구글 서버가 너무 바쁩니다</h3><p>현재 David님의 API 호출 한도가 일시적으로 초과되었습니다. <strong>1시간 뒤에</strong> 자동으로 다시 시도됩니다.</p></div>"
    else:
        error_msg = response.json().get('error', {}).get('message', 'Unknown Error')
        deal_content = f"<div class='deal-card'><h3>🚨 호출 실패 (코드 {response.status_code})</h3><p>{error_msg}</p></div>"
except Exception as e:
    deal_content = f"<div class='deal-card'><h3>🚨 시스템 오류</h3><p>{str(e)}</p></div>"

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
