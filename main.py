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

# 2. 가장 확실한 검색 쿼리 리스트 (단순화)
# 구글 RSS가 잘 인식하도록 복잡한 문법을 제거했습니다.
queries = [
    "반도체 인수합병 매각 지분투자",
    "바이오 헬스케어 인수합병 투자",
    "이차전지 배터리 인수합병 매각"
]

news_context = ""
idx = 1

for q in queries:
    # 안전하게 URL 인코딩 적용
    rss_url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        response = requests.get(rss_url, timeout=10)
        root = ET.fromstring(response.text)
        
        # 각 쿼리당 상위 15개씩 수집
        for item in root.findall('.//item')[:15]:
            title = item.find('title').text
            link = item.find('link').text
            pub_date = item.find('pubDate').text
            news_context += f"[{idx}] 제목: {title}\n날짜: {pub_date}\n링크: {link}\n\n"
            idx += 1
    except:
        continue

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 뉴스 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</h3></div>"
else:
    # 3. AI에게 날짜 판단까지 맡기기 (프롬프트 강화)
    prompt = f"""
    당신은 글로벌 IB의 M&A 애널리스트입니다. 
    제공된 뉴스 리스트에서 '최근 3개월 이내'의 국내 M&A, 지분 투자, 매각 소식만 골라 요약하세요.

    [뉴스 데이터]
    {news_context}

    [작성 규칙]
    1. 반드시 '반도체', '바이오', '배터리', '기타' 카테고리로 분류하세요.
    2. 동일 건에 대한 기사는 하나로 합치고 기사 원문 링크를 최대 3개까지 나열하세요.
    3. 사족이나 인사말 없이 오직 HTML <div> 카드들만 출력하세요.
    4. 진행 중인 사안(추진, 검토)도 포함하세요.
    
    [출력 형식]
    <div class="deal-card" data-category="카테고리명">
      <div class="card-header">
        <span class="category-badge">카테고리명</span>
        <h3>🎯 [대상 업체명] 관련 소식</h3>
      </div>
      <ul>
        <li><strong>주체:</strong> [인수/투자자]</li>
        <li><strong>상태:</strong> [진행상태]</li>
        <li><strong>링크:</strong> <a href="URL1" target="_blank" class="source-link">기사1</a> <a href="URL2" target="_blank" class="source-link">기사2</a></li>
      </ul>
      <h4>핵심 요약</h4>
      <ul><li>내용1</li><li>내용2</li></ul>
    </div>
    """

    model = genai.GenerativeModel(chosen_model_name.replace('models/', ''))
    result = model.generate_content(prompt)
    deal_content = result.text.replace('```html', '').replace('```', '').strip()

# 4. HTML 생성
kst = pytz.timezone('Asia/Seoul')
today_str = datetime.now(kst).strftime("%Y년 %m월 %d일")

html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Domestic M&A Dashboard</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; }}
        .container {{ max-width: 900px; margin: auto; }}
        .filter-container {{ text-align: center; margin-bottom: 30px; }}
        .filter-btn {{ background: #e2e8f0; border: none; padding: 10px 20px; margin: 5px; border-radius: 20px; cursor: pointer; font-weight: bold; }}
        .filter-btn.active {{ background: #1a365d; color: white; }}
        .deal-card {{ background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #2b6cb0; }}
        .category-badge {{ background: #ebf8fa; color: #319795; padding: 3px 10px; border-radius: 10px; font-size: 0.8em; font-weight: bold; }}
        .source-link {{ color: #dd6b20; text-decoration: none; font-weight: bold; margin-right: 10px; background: #feebc8; padding: 2px 5px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1 style="text-align:center;">📊 Domestic M&A Daily Dashboard</h1>
        <p style="text-align:center; font-weight:bold;">업데이트: {today_str}</p>
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
