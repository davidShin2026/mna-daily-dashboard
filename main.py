import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import pytz

# 1. API 키 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
    
    chosen_model_name = None
    for tm in target_models:
        if tm in available_models:
            chosen_model_name = tm
            break
    if not chosen_model_name:
        chosen_model_name = available_models[0] 
except Exception as e:
    print(f"모델 검색 중 에러 발생: {e}")
    raise e

# 2. (핵심 해결책) 복잡한 괄호를 풀고, 섹터별로 3번 나누어 개별 검색
queries = [
    "인수합병 OR 지분투자 OR 매각 반도체 when:3m",
    "인수합병 OR 지분투자 OR 매각 바이오 OR 제약 OR 헬스케어 when:3m",
    "인수합병 OR 지분투자 OR 매각 배터리 OR 2차전지 when:3m"
]

now_utc = datetime.now(timezone.utc)
cutoff_date = now_utc - timedelta(days=90) # 정확히 90일 전 날짜

news_context = ""
valid_count = 0

# 3개의 그물을 차례대로 던져서 기사를 수집합니다.
for query in queries:
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        response = requests.get(rss_url)
        root = ET.fromstring(response.text)
        
        # 각 분야별로 최대 15개씩 골고루 긁어옵니다.
        for item in root.findall('.//item')[:15]:
            if valid_count >= 40: # 전체 기사가 40개가 넘어가면 중단
                break
                
            pubDate_str = item.find('pubDate').text if item.find('pubDate') is not None else ''
            
            # 90일 필터링 적용 (시간대 에러 방지 처리 추가)
            try:
                pubDate_dt = parsedate_to_datetime(pubDate_str)
                if pubDate_dt.tzinfo is None:
                    pubDate_dt = pubDate_dt.replace(tzinfo=timezone.utc)
                if pubDate_dt < cutoff_date:
                    continue # 90일 지난 오래된 기사는 버림
            except:
                pass 
                
            title = item.find('title').text
            link = item.find('link').text
            news_context += f"{valid_count+1}. 제목: {title}\n일자: {pubDate_str}\n링크: {link}\n\n"
            valid_count += 1
    except Exception as e:
        print(f"RSS 검색 에러: {e}")
        continue

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 최근 3개월 내 뉴스 검색 결과가 없습니다.</h3></div>"
else:
    # 3. AI 프롬프트 (요청하신 복수 링크 및 깐깐한 양식 통제)
    prompt = f"""
    당신은 글로벌 IB의 탑티어 M&A 리서치 애널리스트입니다. 
    아래 뉴스를 바탕으로 국내 핵심 섹터의 M&A 및 지분 투자 동향을 요약해 주세요.

    [뉴스 데이터]
    {news_context}

    [엄격한 필수 조건]
    1. **절대 전체 요약, 인사말, 사족을 쓰지 마세요.** 오직 아래 [출력 형식]의 HTML <div> 태그 블록만 출력해야 합니다.
    2. '인수 추진', '매각 검토', '투자 유치' 등 진행 중인 사안도 무조건 딜(Deal)로 간주하고 포함하세요.
    3. 동일한 딜이나 주제에 대한 기사가 여러 개라면, 하나의 카드로 묶고 '기사 원문' 항목에 최대 3개까지 링크를 나열하세요. (예: <a href="링크1">기사 1</a> <a href="링크2">기사 2</a>)
    4. 발견된 딜이 어느 분야인지 판단하여 '반도체', '바이오', '배터리', '기타' 중 1개로 분류하세요.
    5. 발견된 딜의 개수만큼 [출력 형식]을 반복해서 출력하세요.

    [출력 형식 (관련 딜이 있을 때 - 텍스트 없이 오직 이 태그들만 출력할 것)]
    <div class="deal-card" data-category="[반도체/바이오/배터리/기타 중 택 1]">
      <div class="card-header">
        <span class="category-badge">[반도체/바이오/배터리/기타 중 택 1]</span>
        <h3>🎯 [대상 업체명] M&A/투자 동향</h3>
      </div>
      <ul>
        <li><strong>관련 주체:</strong> [인수/투자/매각 관련 업체명]</li>
        <li><strong>진행 상태:</strong> [예: 인수 확정 / 매각 검토 중 등]</li>
        <li><strong>예상 규모:</strong> [금액 또는 미상]</li>
        <li><strong>기사 원문:</strong> <a href="[뉴스 링크 1]" target="_blank" class="source-link">기사 1</a> <a href="[뉴스 링크 2]" target="_blank" class="source-link">기사 2</a></li>
      </ul>
      <h4>주요 내용 요약</h4>
      <ul><li>[기사 핵심 내용 1]</li><li>[기사 핵심 내용 2]</li></ul>
    </div>
    """

    model = genai.GenerativeModel(chosen_model_name.replace('models/', ''))
    result = model.generate_content(prompt)
    deal_content = result.text.replace('```html', '').replace('```', '').strip()

# 4. HTML 디자인 템플릿 (필터링 스크립트 포함)
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")

html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Domestic M&A Daily Dashboard</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; color: #333; }}
        .container {{ max-width: 900px; margin: auto; }}
        h1 {{ color: #1a365d; text-align: center; margin-bottom: 5px; }}
        .date {{ text-align: center; color: #718096; margin-bottom: 25px; font-weight: bold; font-size: 0.9em; }}
        
        .filter-container {{ text-align: center; margin-bottom: 30px; }}
        .filter-btn {{
            background-color: #e2e8f0; border: none; padding: 8px 18px; margin: 0 5px; 
            border-radius: 20px; cursor: pointer; font-weight: bold; color: #4a5568;
            transition: all 0.2s ease-in-out; font-size: 0.9em;
        }}
        .filter-btn:hover {{ background-color: #cbd5e1; }}
        .filter-btn.active {{ background-color: #1a365d; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}

        .deal-card {{ background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; transition: display 0.3s; border: 1px solid #e2e8f0; }}
        .card-header {{ display: flex; align-items: center; border-bottom: 2px solid #edf2f7; padding-bottom: 12px; margin-bottom: 15px; }}
        .category-badge {{ background-color: #ebf8fa; color: #319795; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 800; margin-right: 15px; border: 1px solid #b2f5ea; }}
        .deal-card h3 {{ color: #2d3748; margin: 0; font-size: 1.3em; }}
        
        ul {{ line-height: 1.7; }}
        
        .source-link {{ color: #dd6b20; text-decoration: none; font-weight: bold; background-color: #feebc8; padding: 3px 10px; border-radius: 6px; margin-right: 5px; font-size: 0.9em; display: inline-block; margin-bottom: 3px; }}
        .source-link:hover {{ background-color: #fbd38d; text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Domestic M&A Daily Dashboard</h1>
        <div class="date">업데이트: {today_str} 오전 8:10</div>
        
        <div class="filter-container">
            <button class="filter-btn active" onclick="filterDeals('전체')">전체보기</button>
            <button class="filter-btn" onclick="filterDeals('반도체')">반도체</button>
            <button class="filter-btn" onclick="filterDeals('바이오')">바이오</button>
            <button class="filter-btn" onclick="filterDeals('배터리')">배터리</button>
            <button class="filter-btn" onclick="filterDeals('기타')">기타</button>
        </div>

        <div id="deal-list">
            {deal_content}
        </div>
    </div>

    <script>
        function filterDeals(category) {{
            const buttons = document.querySelectorAll('.filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            const cards = document.querySelectorAll('.deal-card');
            cards.forEach(card => {{
                const cardCategory = card.getAttribute('data-category');
                if (category === '전체' || cardCategory === category) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
