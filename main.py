import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET
import google.generativeai as genai
from datetime import datetime
import pytz
import time

# 1. API 키 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
    chosen_model_name = next((tm for tm in target_models if tm in available_models), available_models[0])
except Exception as e:
    print(f"모델 설정 에러: {e}")
    raise e

news_context = ""
idx = 1
seen_titles = set()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

# 가짜 딜(단순 투자, 실적) 제외 필터
exclude_keywords = ["설비", "시설", "연구개발", "R&D", "공장", "증설", "채용", "사옥", "실적", "영업이익"]

# ==========================================
# 트랙 1: 구글 뉴스 (단순 쿼리로 6개월 치 과거 데이터 확보)
# ==========================================
google_queries = [
    "반도체 M&A when:6m", "반도체 인수합병 when:6m", "반도체 지분인수 when:6m",
    "바이오 M&A when:6m", "바이오 인수합병 when:6m",
    "배터리 M&A when:6m", "이차전지 경영권 when:6m"
]

for q in google_queries:
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            for item in root.findall('.//item')[:5]: # 쿼리당 핵심 5개씩
                title = item.find('title').text
                link = item.find('link').text
                pub_date = item.find('pubDate').text
                
                if any(bad in title for bad in exclude_keywords): continue
                if title not in seen_titles:
                    seen_titles.add(title)
                    news_context += f"[{idx}] 제목: {title}\n날짜: {pub_date}\n링크: {link}\n\n"
                    idx += 1
        time.sleep(1) # 차단 방지 휴식
    except:
        continue

# ==========================================
# 트랙 2: 10대 언론사 직통 RSS (구글 차단 대비 및 최신 딜 확보)
# ==========================================
media_rss = [
    "https://rss.hankyung.com/feed/economy.xml", "https://rss.hankyung.com/feed/it.xml",
    "https://www.mk.co.kr/rss/30100041/", "https://www.mk.co.kr/rss/50300009/", 
    "https://www.yna.co.kr/rss/economy.xml", "https://rss.etnews.com/Section902.xml"
]
deal_keywords = ["인수", "합병", "M&A", "매각", "지분", "투자", "상장", "IPO"]

for url in media_rss:
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            for item in root.findall('.//item'):
                title = item.find('title').text
                link = item.find('link').text
                pub_date_elem = item.find('pubDate')
                pub_date = pub_date_elem.text if pub_date_elem is not None else "최근"
                
                if title and any(k in title for k in deal_keywords) and not any(bad in title for bad in exclude_keywords):
                    if title not in seen_titles and idx <= 60:
                        seen_titles.add(title)
                        news_context += f"[{idx}] 제목: {title}\n날짜: {pub_date}\n링크: {link}\n\n"
                        idx += 1
    except:
        continue

# ==========================================
# 3. AI 분석 및 HTML 생성
# ==========================================
if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 뉴스 데이터를 불러오지 못했습니다. 서버 상태를 확인해 주세요.</h3></div>"
else:
    prompt = f"""
    당신은 글로벌 IB의 시니어 M&A 애널리스트입니다. 
    제공된 뉴스 리스트에서 '반도체, 바이오, 배터리' 섹터의 '인수합병(M&A), 지분 투자, 경영권 매각, 상장(IPO)' 소식만을 엄격하게 골라 요약하세요. 

    [뉴스 데이터]
    {news_context}

    [작성 규칙]
    1. 반드시 '반도체', '바이오', '배터리', '기타' 카테고리로 분류하세요. (이차전지는 '배터리'로 통일)
    2. 동일 건에 대한 기사는 하나로 묶고 기사 링크를 나열하세요.
    3. 사족이나 인사말 없이 오직 HTML <div> 카드들만 출력하세요.
    4. 기사의 '날짜' 데이터를 확인하여, 딜 발생 일자를 헤드라인(<h3>) 앞에 [YYYY.MM.DD] 형식으로 포함하세요.
    
    [출력 형식]
    <div class="deal-card" data-category="카테고리명">
      <div class="card-header">
        <span class="category-badge">카테고리명</span>
        <h3>🎯 [YYYY.MM.DD] [대상 업체명] 관련 소식</h3>
      </div>
      <ul>
        <li><strong>주체:</strong> [인수/투자자]</li>
        <li><strong>상태:</strong> [진행상태]</li>
        <li><strong>링크:</strong> <a href="URL1" target="_blank" class="source-link">기사1</a></li>
      </ul>
      <h4>핵심 요약</h4>
      <ul><li>내용1</li><li>내용2</li></ul>
    </div>
    """
    model = genai.GenerativeModel(chosen_model_name.replace('models/', ''))
    result = model.generate_content(prompt)
    deal_content = result.text.replace('```html', '').replace('```', '').strip()

kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")

html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>M&A News for ISU OI Team</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; }}
        .container {{ max-width: 900px; margin: auto; }}
        .header-container {{ display: flex; align-items: center; justify-content: center; margin-bottom: 25px; border-bottom: 2px solid #1a365d; padding-bottom: 15px; }}
        .isu-logo {{ max-height: 45px; margin-right: 18px; vertical-align: middle; }}
        .isu-title {{ margin: 0; font-size: 2.3em; color: #1a365d; }}
        .filter-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-bottom: 30px; }}
        .filter-btn {{ background: #e2e8f0; border: none; padding: 10px 20px; border-radius: 20px; cursor: pointer; font-weight: bold; font-size: 1em; transition: 0.2s; }}
        .filter-btn.active {{ background: #1a365d; color: white; }}
        .deal-card {{ background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #2b6cb0; line-height: 1.6; }}
        .card-header {{ display: flex; align-items: center; border-bottom: 2px solid #edf2f7; padding-bottom: 12px; margin-bottom: 15px; }}
        .category-badge {{ background: #ebf8fa; color: #319795; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: bold; margin-right: 15px; border: 1px solid #b2f5ea; }}
        .deal-card h3 {{ margin: 0; font-size: 1.25em; color: #2d3748; }}
        .source-link {{ color: #dd6b20; text-decoration: none; font-weight: bold; margin-right: 8px; background: #feebc8; padding: 3px 8px; border-radius: 4px; display: inline-block; margin-bottom: 4px; }}
        @media (max-width: 600px) {{
            body {{ padding: 15px; }}
            h1 {{ font-size: 1.5em; }}
            .isu-title {{ font-size: 1.6em; line-height: 1.2; text-align: center; }}
            .header-container {{ flex-direction: column; }}
            .isu-logo {{ max-height: 35px; margin-right: 0; margin-bottom: 10px; }}
            .filter-btn {{ padding: 12px 16px; font-size: 1.1em; flex-grow: 1; text-align: center; }}
            .deal-card {{ padding: 15px; }}
            .category-badge {{ padding: 3px 8px; font-size: 0.8em; margin-right: 10px; }}
            .deal-card h3 {{ font-size: 1.15em; line-height: 1.3; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-container">
            <img src="ISU CI.png" class="isu-logo" alt="ISU Group Logo">
            <h1 class="isu-title">M&A News for ISU OI Team</h1>
        </div>
        <p style="text-align:center; font-weight:bold; color:#718096; margin-bottom: 25px;">업데이트: {today_str}</p>
        
        <div class="filter-container">
            <button class="filter-btn active" onclick="filterDeals('전체')">전체보기</button>
            <button class="filter-btn" onclick="filterDeals('반도체')">반도체</button>
            <button class="filter-btn" onclick="filterDeals('바이오')">바이오</button>
            <button class="filter-btn" onclick="filterDeals('배터리')">배터리</button>
            <button class="filter-btn" onclick="filterDeals('기타')">기타</button>
        </div>
        
        <div id="deal-list">{deal_content}</div>
    </div>
    <script>
        function filterDeals(cat) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            document.querySelectorAll('.deal-card').forEach(c => {{
                c.style.display = (cat === '전체' || c.getAttribute('data-category') === cat) ? 'block' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
