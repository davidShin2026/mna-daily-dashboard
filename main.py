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

# 2. 네이버 뉴스 수집 로직 (섹터별로 골고루 수집)
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
                if title not in seen_titles and idx <= 25:
                    seen_titles.add(title)
                    news_context += f"[{idx}] {title}\n"
                    news_list_html += f"<li><a href='{link}' target='_blank'>{title}</a></li>"
                    idx += 1
    except: continue

# 3. Gemini API 호출 (성공률 극대화 전략)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 무료 티어에서 가장 응답이 확실한 모델 순서입니다.
MODELS = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]
deal_content = ""

prompt = f"당신은 IB 애널리스트입니다. 아래 뉴스 목록에서 M&A 및 투자 관련 핵심 내용을 섹터별(반도체, 바이오, 기타 등)로 분류하여 요약하세요. 결과는 반드시 HTML <div> 카드 형식으로만 출력하고 사족은 절대 생략하세요. 오늘날짜: {today_badge}\n\n뉴스:\n{news_context}"

for model_id in MODELS:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        # 호출 전 구글 서버를 진정시키기 위해 10초간 대기 (매우 중요!)
        time.sleep(10)
        response = requests.post(url, json=payload, timeout=40)
        if response.status_code == 200:
            res_json = response.json()
            deal_content = res_json['candidates'][0]['content']['parts'][0]['text']
            deal_content = re.sub(r'```html|```', '', deal_content).strip()
            print(f"✅ {model_id} 요약 성공!")
            break
        else:
            print(f"❌ {model_id} 실패 (코드 {response.status_code})")
    except: continue

# 4. 보험 로직: AI 실패 시에도 리스트는 보여줌
if not deal_content or "<div" not in deal_content:
    deal_content = f"""
    <div class='deal-card'>
        <h3>📰 오늘의 실시간 M&A 뉴스 리스트</h3>
        <p style='color: #718096; font-size: 0.9em;'>현재 AI 분석 엔진이 데이터 처리 중입니다. 아래 링크를 통해 원문을 바로 확인하실 수 있습니다.</p>
        <ul style='margin-top: 15px; padding-left: 20px;'>{news_list_html}</ul>
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
