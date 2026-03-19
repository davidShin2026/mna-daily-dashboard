import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
from datetime import datetime
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

# 2. 국내 한정 + 기간 1년 + URL 안전 인코딩
query = "국내 (인수합병 OR 지분투자 OR 매각 OR 경영권) (반도체 OR 바이오 OR 제약 OR 헬스케어 OR 배터리 OR 2차전지) when:1y"
encoded_query = urllib.parse.quote(query)
rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

response = requests.get(rss_url)
root = ET.fromstring(response.text)

news_context = ""
for i, item in enumerate(root.findall('.//item')[:30]):
    title = item.find('title').text
    link = item.find('link').text
    pubDate = item.find('pubDate').text if item.find('pubDate') is not None else '날짜 미상'
    # 프롬프트에서 활용할 수 있도록 '링크' 항목을 확실하게 전달합니다.
    news_context += f"{i+1}. 제목: {title}\n일자: {pubDate}\n링크: {link}\n\n"

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 뉴스 검색 결과가 없습니다.</h3></div>"
else:
    # 3. (핵심) 원문 링크 추가 및 카테고리 분류 지시
    prompt = f"""
    당신은 글로벌 IB의 탑티어 M&A 리서치 애널리스트입니다. 
    아래 뉴스를 바탕으로 국내 핵심 섹터의 M&A 및 지분 투자 동향을 요약해 주세요.

    [뉴스 데이터]
    {news_context}

    [필수 조건]
    1. 완벽히 확정된 딜이 아니더라도, '인수 추진', '매각 검토', '투자 유치', 'MOU 체결' 등 진행 중인 사안이라면 포함하세요.
    2. 발견된 딜이 어느 분야인지 판단하여 '반도체', '바이오', '배터리', '기타' 중 1개로 분류하세요. (제약/헬스케어는 '바이오', 2차전지는 '배터리'로 통일)
    3. 팀원들이 확인할 수 있도록 반드시 뉴스 데이터에 제공된 '링크'를 추출하여 [출력 형식 1]의 <a> 태그 안에 넣으세요.
    4. 여러 개의 소식이 있다면 아래 [출력 형식 1]의 HTML <div> 태그 블록을 소식의 개수만큼 반복해서 모두 출력하세요.

    [출력 형식 1 (관련 딜이 있을 때 - 개수만큼 반복 출력)]
    <div class="deal-card" data-category="[반도체/바이오/배터리/기타 중 택 1]">
      <div class="card-header">
        <span class="category-badge">[반도체/바이오/배터리/기타 중 택 1]</span>
        <h3>🎯 [대상 업체명] M&A/투자 동향</h3>
      </div>
      <ul>
        <li><strong>관련 주체:</strong> [인수/투자/매각 관련 업체명]</li>
        <li><strong>진행 상태:</strong> [예: 인수 확정 / 매각 검토 중 등]</li>
        <li><strong>예상 규모:</strong> [금액 또는 미상]</li>
        <li><strong>기사 원문:</strong> <a href="[뉴스 원문 링크 URL]" target="_blank" class="source-link">바로가기 (클릭)</a></li>
      </ul>
      <h4>주요 내용 요약</h4>
      <ul><li>[기사 핵심 내용 1]</li><li>[기사 핵심 내용 2]</li></ul>
    </div>

    [출력 형식 2 (관련 소식이 전혀 없을 때)]
    <div class="deal-card" data-category="기타">
      <h3 style="color:#e53e3e;">🎯 확인된 주요 M&A 딜 없음</h3>
      <p>수집된 뉴스 중 유의미한 인수합병 및 지분 투자 소식이 없습니다.</p>
    </div>
    """

    model = genai.GenerativeModel(chosen_model_name.replace('models/', ''))
    result = model.generate_content(prompt)
    deal_content = result.text

# 4. (핵심) 필터 버튼 및 자바스크립트 추가
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
        
        /* 필터 버튼 디자인 */
        .filter-container {{ text-align: center; margin-bottom: 30px; }}
        .filter-btn {{
            background-color: #e2e8f0; border: none; padding: 8px 18px; margin: 0 5px; 
            border-radius: 20px; cursor: pointer; font-weight: bold; color: #4a5568;
            transition: all 0.2s ease-in-out; font-size: 0.9em;
        }}
        .filter-btn:hover {{ background-color: #cbd5e1; }}
        .filter-btn.active {{ background-color: #1a365d; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}

        /* 카드 디자인 및 뱃지 */
        .deal-card {{ background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; transition: display 0.3s; border: 1px solid #e2e8f0; }}
        .card-header {{ display: flex; align-items: center; border-bottom: 2px solid #edf2f7; padding-bottom: 12px; margin-bottom: 15px; }}
        .category-badge {{ background-color: #ebf8fa; color: #319795; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 800; margin-right: 15px; border: 1px solid #b2f5ea; }}
        .deal-card h3 {{ color: #2d3748; margin: 0; font-size: 1.3em; }}
        
        ul {{ line-height: 1.7; }}
        
        /* 기사 원문 링크 강조 */
        .source-link {{ color: #dd6b20; text-decoration: none; font-weight: bold; background-color: #feebc8; padding: 2px 8px; border-radius: 6px; }}
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
            // 1. 눌린 버튼에 색상(active) 입히기
            const buttons = document.querySelectorAll('.filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // 2. 카테고리에 맞는 카드만 보여주고 나머지는 숨기기
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
