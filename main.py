import os
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
from datetime import datetime
import pytz

# 1. API 키 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
    chosen_model_name = next((tm for tm in target_models if tm in available_models), available_models[0])
except Exception as e:
    print(f"모델 설정 에러: {e}")
    raise e

# 2. 메이저 언론사 15곳 메가 파이프라인 (경제지, 종합지, 통신사, IT전문지)
rss_feeds = [
    # 경제/비즈니스
    "https://rss.hankyung.com/feed/economy.xml",
    "https://rss.hankyung.com/feed/it.xml",
    "https://rss.hankyung.com/feed/industry.xml",
    "https://www.mk.co.kr/rss/30100041/", # 매경 기업
    "https://www.mk.co.kr/rss/50300009/", # 매경 IT
    "https://www.mk.co.kr/rss/50200011/", # 매경 증권
    "https://biz.sbs.co.kr/rss/economy.xml", # SBS Biz
    # 종합지/통신사
    "https://www.yna.co.kr/rss/economy.xml", # 연합뉴스 경제
    "https://www.yna.co.kr/rss/industry.xml", # 연합뉴스 산업
    "https://rss.donga.com/economy.xml", # 동아일보 경제
    "https://rss.joins.com/joins_money_list.xml", # 중앙일보 경제
    # IT/기술 전문
    "https://rss.etnews.com/Section902.xml", # 전자신문 기업
    "https://rss.etnews.com/Section903.xml", # 전자신문 부품소재
    "https://rss.etnews.com/Section904.xml", # 전자신문 과학
    "https://www.bloter.net/rss/allArticle.xml" # 블로터(IT/스타트업)
]

# 확장된 자본 거래(Deal) 뜰채 키워드 (초기 딜부터 Exit까지)
deal_keywords = [
    "인수", "합병", "M&A", "매각", "지분", "투자", "상장", "IPO", 
    "시리즈", "펀드", "스타트업", "벤처", "스팩", "SPAC", "합작", "JV"
]

news_context = ""
idx = 1
seen_titles = set()

# 차단 방지 헤더
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
}

for url in rss_feeds:
    try:
        # 타임아웃을 5초로 줄여 응답 없는 사이트는 빠르게 버리고 넘어감
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            continue
            
        root = ET.fromstring(response.text)
        
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            pub_date_elem = item.find('pubDate')
            pub_date = pub_date_elem.text if pub_date_elem is not None else "오늘"
            
            if title and any(k in title for k in deal_keywords):
                # 중복 기사 필터링 및 토큰 한도 초과 방지 (최대 60개까지만 수집)
                if title not in seen_titles and idx <= 60:
                    seen_titles.add(title)
                    news_context += f"[{idx}] 제목: {title}\n날짜: {pub_date}\n링크: {link}\n\n"
                    idx += 1
                    
    except Exception as e:
        # 특정 언론사 서버 에러 시 무시하고 다음으로 진행
        continue

# 3. AI 분석 엔진
if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#718096;'>🎯 오늘 업데이트된 국내 주요 M&A 및 투자 소식이 없습니다.</h3></div>"
else:
    prompt = f"""
    당신은 글로벌 IB의 시니어 M&A 애널리스트입니다. 
    제공된 경제 기사 리스트에서 '반도체, 바이오, 배터리' 섹터와 관련된 M&A, 지분 투자, 상장 소식만을 '엄격하게' 선별하여 요약하세요. 
    단순 제품 출시, 실적 발표, 인사 이동 등 자본 거래와 무관한 기사는 절대 포함하지 마세요.

    [뉴스 데이터]
    {news_context}

    [작성 규칙]
    1. 반드시 '반도체', '바이오', '배터리', '기타(자본거래 확실한 건만)' 카테고리로 분류하세요. (이차전지는 '배터리'로 통일)
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

# 4. HTML 생성 (ISU OI Team 로고 UI 유지)
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
