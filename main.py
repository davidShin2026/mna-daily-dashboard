import os
import requests
import json
import urllib.parse
from datetime import datetime
import pytz
import re

# 1. 환경 변수 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
NAVER_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

# 2. 네이버 뉴스 수집 로직
queries = [
    "반도체 M&A", "반도체 인수합병", "바이오 M&A", "바이오 인수합병",
    "배터리 M&A", "이차전지 투자유치", "스타트업 시리즈A 투자"
]
exclude_keywords = ["설비", "공장", "증설", "채용", "주가", "특징주"]

news_context = ""
idx = 1
seen_titles = set()
headers_naver = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}

def clean_html(raw_html):
    return re.sub('<.*?>', '', raw_html).replace('&quot;', '"').replace('&amp;', '&')

for q in queries:
    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=50&sort=sim"
    try:
        res = requests.get(url, headers=headers_naver, timeout=10)
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

# 3. Gemini API 호출 (복수 모델 자동 시도 로직)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")
today_badge = datetime.now(kst).strftime("%Y.%m.%d")

# 시도해볼 모델 명칭 리스트 (가장 표준적인 이름들입니다)
MODELS_TO_TRY = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
deal_content = ""

prompt = f"""
당신은 글로벌 IB의 시니어 M&A 애널리스트입니다. 아래 뉴스에서 '반도체, 바이오, 배터리, 기타' 섹터 자본 거래를 정리하세요.
오늘 날짜는 [{today_badge}]입니다. 오늘 뉴스는 <h3> 안에 <span class="new-badge">NEW</span>를 꼭 붙이세요.
반드시 HTML <div> 카드 형식으로만 출력하세요. 사족은 절대 금지합니다.

[뉴스 리스트]
{news_context}
"""

# 모델을 하나씩 돌아가며 호출해봅니다.
for model_id in MODELS_TO_TRY:
    # v1과 v1beta 모두 대응할 수 있도록 v1을 우선 시도합니다.
    url = f"https://generativelanguage.googleapis.com/v1/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            response_data = response.json()
            deal_content = response_data['candidates'][0]['content']['parts'][0]['text']
            deal_content = deal_content.replace('```html', '').replace('```', '').strip()
            print(f"✅ 성공한 모델: {model_id}")
            break # 성공하면 반복 중단
        else:
            print(f"❌ {model_id} 실패 (코드 {response.status_code})")
    except Exception as e:
        print(f"⚠️ {model_id} 연결 오류: {e}")
        continue

if not deal_content:
    deal_content = f"<div class='deal-card'><h3>🚨 모든 AI 모델 호출에 실패했습니다.</h3><p>API 키 권한이나 구글 클라우드 설정을 점검해 주세요.</p></div>"

# 4. HTML 대시보드 생성
html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>M&A News for ISU OI Team</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; }}
        .container {{ max-width: 900px; margin: auto; }}
        .header-container {{ text-align: center; border-bottom: 2px solid #1a365d; padding-bottom: 15px; margin-bottom: 25px; }}
        .isu-title {{ font-size: 2.3em; color: #1a365d; }}
        .deal-card {{ background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #2b6cb0; }}
        .new-badge {{ background-color: #e53e3e; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; margin-right: 8px; }}
        .category-badge {{ background: #ebf8fa; color: #319795; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: bold; margin-right: 15px; border: 1px solid #b2f5ea; }}
        .source-link {{ color: #dd6b20; font-weight: bold; text-decoration: none; background: #feebc8; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 5px; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-container">
            <h1 class="isu-title">M&A News for ISU OI Team</h1>
            <p style="color:#718096; font-weight:bold;">업데이트: {today_str}</p>
        </div>
        <div id="deal-list">{deal_content}</div>
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
