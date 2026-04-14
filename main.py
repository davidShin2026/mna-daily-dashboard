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
news_context = ""
news_list_html = ""
idx = 1
seen_titles = set()
headers_naver = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}

def clean_html(raw_html):
    return re.sub('<.*?>', '', raw_html).replace('&quot;', '"').replace('&amp;', '&')

for q in queries:
    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=10&sort=sim"
    try:
        res = requests.get(url, headers=headers_naver, timeout=10)
        if res.status_code == 200:
            for item in res.json().get('items', []):
                title = clean_html(item['title'])
                link = item['originallink'] or item['link']
                if title not in seen_titles and idx <= 20:
                    seen_titles.add(title)
                    news_context += f"[{idx}] {title}\n"
                    news_list_html += f"<li><a href='{link}' target='_blank'>{title}</a></li>"
                    idx += 1
    except: continue

# 3. Gemini API 호출 (최경량 모델 사용)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 가장 가벼운 8b 모델을 사용하여 성공 확률을 높입니다.
model_id = "gemini-1.5-flash-8b"
deal_content = ""
prompt = f"당신은 IB 애널리스트입니다. 아래 뉴스에서 M&A 및 투자 관련 내용을 섹터별로 요약하세요. HTML <div> 카드 형식으로만 출력하세요. 사족 금지. 오늘날짜: {today_badge}\n\n뉴스:\n{news_context}"

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
payload = {"contents": [{"parts": [{"text": prompt}]}]}

# 구글 서버를 달래기 위해 실행 전 5초 대기
time.sleep(5)
try:
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        res_json = response.json()
        deal_content = res_json['candidates'][0]['content']['parts'][0]['text']
        deal_content = re.sub(r'```html|```', '', deal_content).strip()
    else:
        print(f"❌ API 응답 실패 (코드 {response.status_code})")
except: pass

# 4. 보험 로직: AI가 실패하면 뉴스 목록이라도 출력
if not deal_content or "<div" not in deal_content:
    deal_content = f"""
    <div class='deal-card'>
        <h3>📰 오늘의 주요 M&A 뉴스 목록</h3>
        <p style='color: #718096; font-size: 0.9em;'>현재 AI 요약 엔진이 바빠서 원문 링크를 먼저 공유해 드립니다.</p>
        <ul style='margin-top: 15px; padding-left: 20px; color: #2d3748;'>{news_list_html}</ul>
    </div>
    """

# 5. HTML 대시보드 생성
html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>M&A News for ISU OI Team</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; color: #2d3748; line-height: 1.6; }}
        .container {{ max-width: 900px; margin: auto; }}
        .header {{ text-align: center; border-bottom: 2px solid #1a365d; padding-bottom: 15px; margin-bottom: 25px; }}
        .deal-card {{ background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; border-left: 6px solid #1a365d; }}
        h3 {{ color: #1a365d; margin-top: 0; border-bottom: 1px solid #edf2f7; padding-bottom: 10px; }}
        ul {{ list-style-type: square; }}
        li {{ margin-bottom: 10px; }}
        a {{ color: #2b6cb0; text-decoration: none; font-weight: bold; }}
        a:hover {{ text-decoration: underline; }}
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
