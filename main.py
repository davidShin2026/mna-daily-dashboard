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
queries = ["반도체 M&A", "바이오 인수합병", "배터리 투자유치"]
news_context = ""
news_list_html = ""
idx = 1
seen_titles = set()
headers_naver = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}

def clean_html(raw_html):
    return re.sub('<.*?>', '', raw_html).replace('&quot;', '"').replace('&amp;', '&')

for q in queries:
    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=15&sort=sim"
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

# 3. Gemini API 호출 (자동 재시도 로직)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 어제 429 응답을 주었던(인증에 성공한) 모델을 집중 공략합니다.
model_id = "gemini-2.0-flash"
deal_content = ""
prompt = f"당신은 IB 애널리스트입니다. 아래 뉴스에서 M&A 및 투자 관련 내용을 섹터별로 요약하세요. HTML <div> 카드 형식으로만 출력하세요. 사족 금지. 오늘날짜: {today_badge}\n\n뉴스:\n{news_context}"

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
payload = {"contents": [{"parts": [{"text": prompt}]}]}

for attempt in range(2): # 최대 2번 시도
    try:
        if attempt > 0: time.sleep(15) # 429 발생 시 15초 대기 후 재시도
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            res_json = response.json()
            deal_content = res_json['candidates'][0]['content']['parts'][0]['text']
            deal_content = re.sub(r'```html|```', '', deal_content).strip()
            print(f"✅ {model_id} 호출 성공!")
            break
        else:
            print(f"❌ 시도 {attempt+1} 실패 (코드 {response.status_code})")
    except: continue

# 요약 실패 시 '뉴스 리스트'라도 보여주는 보험 로직
if not deal_content:
    deal_content = f"""
    <div class='deal-card'>
        <h3>⚠️ 요약 엔진 일시 점검 중</h3>
        <p>구글 API 한도 초과로 자동 요약이 지연되고 있습니다. 대신 오늘 수집된 주요 뉴스 목록을 공유드립니다.</p>
        <ul style='font-size: 0.9em; color: #4a5568;'>{news_list_html}</ul>
        <p style='font-size: 0.8em; color: #a0aec0;'>* 잠시 후 [Actions]에서 다시 실행하면 요약 기능이 복구됩니다.</p>
    </div>
    """

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
        .deal-card {{ background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #2b6cb0; line-height: 1.6; }}
        h3 {{ color: #2b6cb0; margin-top: 0; }}
        a {{ color: #2d3748; text-decoration: none; }}
        a:hover {{ text-decoration: underline; color: #2b6cb0; }}
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
