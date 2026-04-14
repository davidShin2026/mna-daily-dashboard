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
                if title not in seen_titles and idx <= 25:
                    seen_titles.add(title)
                    news_context += f"[{idx}] {title}\n"
                    news_list_html += f"<li><a href='{link}' target='_blank'>{title}</a></li>"
                    idx += 1
    except: continue

# 3. Gemini API 호출 (안정적인 모델 명단 적용)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 가장 표준적인 모델 명칭입니다.
STRATEGIES = [
    ("v1beta", "gemini-1.5-flash"),
    ("v1beta", "gemini-2.0-flash")
]

deal_content = ""
prompt = f"당신은 IB 애널리스트입니다. 아래 뉴스에서 M&A 및 투자 관련 내용을 섹터별로 요약하세요. HTML <div> 카드 형식으로만 출력하세요. 사족 금지. 오늘날짜: {today_badge}\n\n뉴스:\n{news_context}"

for version, model_id in STRATEGIES:
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        # 호출 전 3초간 휴식 (429 에러 방지)
        time.sleep(3)
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            res_json = response.json()
            deal_content = res_json['candidates'][0]['content']['parts'][0]['text']
            # 마크다운 코드 블록 제거
            deal_content = re.sub(r'```html|```', '', deal_content).strip()
            print(f"✅ {model_id} 요약 성공!")
            break
        else:
            print(f"❌ {model_id} 실패 (코드 {response.status_code})")
    except: continue

# 4. 보험 로직: AI가 실패하면 뉴스 목록이라도 출력
if not deal_content or "<div" not in deal_content:
    deal_content = f"""
    <div class='deal-card'>
        <h3>📰 오늘의 주요 M&A 뉴스 목록</h3>
        <p style='color: #718096; font-size: 0.9em;'>AI 요약 엔진이 잠시 응답하지 않아 원문 링크 리스트를 먼저 제공합니다.</p>
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
        li {{ margin-bottom: 8px; }}
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
