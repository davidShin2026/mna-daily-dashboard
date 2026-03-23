import os
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
from datetime import datetime
import pytz
import time
import urllib.parse

# 1. API 키 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
    chosen_model_name = next((tm for tm in target_models if tm in available_models), available_models[0])
except Exception as e:
    print(f"모델 설정 에러: {e}")
    raise e

# 2. 검색 쿼리 잘게 쪼개기 (구글 RSS 에러 방지 및 다양성 확보)
queries = [
    # 반도체/소부장
    "반도체 M&A OR 인수 OR 매각 OR Exit",
    "반도체 지분 OR 경영권 OR 투자",
    "반도체 IPO OR 상장 OR Pre-IPO",
    "반도체 시리즈A OR 시리즈B OR 시리즈C OR 시드 투자",
    # 바이오/헬스케어
    "바이오 M&A OR 인수 OR 매각 OR Exit",
    "바이오 지분 OR 경영권 OR 투자",
    "바이오 IPO OR 상장 OR Pre-IPO",
    "바이오 시리즈A OR 시리즈B OR 시리즈C OR 시드 투자",
    # 배터리/이차전지
    "배터리 M&A OR 인수 OR 매각 OR Exit",
    "이차전지 지분 OR 경영권 OR 투자",
    "이차전지 IPO OR 상장 OR Pre-IPO",
    "이차전지 시리즈A OR 시리즈B OR 시리즈C OR 시드 투자"
]

news_context = ""
idx = 1
seen_links = set()

# 구글 봇 차단 우회를 위한 스텔스 엔진 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

for q in queries:
    # 6개월 조건(when:6m) 추가 및 안전한 인코딩을 위해 urllib.parse 사용
    encoded_query = urllib.parse.quote(f"{q} when:6m")
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    # 봇 차단 우회를 위한 리트라이 메커니즘 (with Exponential Backoff)
    max_retries = 3
    retry_delay = 3
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            # 성공 시 루프 탈출
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                # 각 쿼리당 상위 10개씩 골라 담기
                for item in root.findall('.//item')[:10]:
                    title = item.find('title').text
                    link = item.find('link').text
                    pub_date = item.find('pubDate').text
                    
                    if link not in seen_links:
                        seen_links.add(link)
                        news_context += f"[{idx}] 제목: {title}\n날짜: {pub_date}\n링크: {link}\n\n"
                        idx += 1
                break
                
            # 봇 차단(429 또는 403) 시 대기 후 재시도
            elif response.status_code in [429, 403]:
                print(f"[Attempt {attempt+1}/{max_retries}] 구글 서버 차단: {q}. {retry_delay}초 후 재시도합니다.")
                time.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff (3s -> 6s -> 12s)
            
            else:
                print(f"[Attempt {attempt+1}/{max_retries}] 접속 실패: {q}. {response.status_code}")
                break
                
        except Exception as e:
            print(f"[{q}] 파싱 에러: {e}")
            break
            
    # 연속 요청으로 인한 IP 차단을 막기 위해 2초 대기 (안정성 강화)
    time.sleep(2)

# 기사를 하나도 못 가져왔을 때의 예외 처리
if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 뉴스 데이터를 불러오지 못했습니다. 깃허브 Actions 로그를 확인해 주세요.</h3></div>"
else:
    # AI 프롬프트 (M&A New for ISU OI Team 요약 및 분류 지시)
    prompt = f"""
    당신은 글로벌 IB의 M&A 애널리스트입니다. 
    제공된 뉴스 리스트에서 국내 반도체, 바이오, 배터리 관련 투자 및 M&A 소식만 골라 요약하세요.

    [뉴스 데이터]
    {news_context}

    [작성 규칙]
    1. 반드시 '반도체', '바이오', '배터리', '기타' 카테고리로 분류하세요. (이차전지는 '배터리'로 통일)
    2. M&A, 지분 인수/매각, 경영권 변동, IPO, Pre-IPO, 시리즈 A/B/C, 시드 투자 등 모든 형태의 자본 거래를 빠짐없이 포함하세요.
    3. 동일 건에 대한 기사는 하나로 합치고 기사 원문 링크를 나열하세요.
    4. 사족이나 인사말 없이 오직 HTML <div> 카드들만 출력하세요.
    5. 기사의 '날짜' 데이터를 확인하여, 딜 발생 일자를 헤드라인(<h3>) 앞에 [YYYY.MM.DD] 형식으로 포함하세요. 
    
    [출력 형식]
    <div class="deal-card" data-category="카테고리명">
      <div class="card-header">
        <span class="category-badge">카테고리명</span>
        <h3>🎯 [YYYY.MM.DD] [대상 업체명] 관련 소식</h3>
      </div>
      <ul>
        <li><strong>주체:</strong> [인수/투자자]</li>
        <li><strong>상태:</strong> [진행상태 (예: 시리즈A 투자 유치, 경영권 매각 완료 등)]</li>
        <li><strong>링크:</strong> <a href="URL1" target="_blank" class="source-link">기사1</a> <a href="URL2" target="_blank" class="source-link">기사2</a></li>
      </ul>
      <h4>핵심 요약</h4>
      <ul><li>내용1</li><li>내용2</li></ul>
    </div>
    """

    model = genai.GenerativeModel(chosen_model_name.replace('models/', ''))
    result = model.generate_content(prompt)
    deal_content = result.text.replace('```html', '').replace('```', '').strip()

# 4. HTML 생성 (M&A News for ISU OI Team 고도화 UI 디자인 적용)
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
        
        /* 헤더 고도화 (로고/제목 flexbox 적용) */
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
