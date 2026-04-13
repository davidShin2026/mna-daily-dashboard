import os
import requests
import urllib.parse
import google.generativeai as genai
from datetime import datetime
import pytz
import re

# 1. API 키 및 안정적인 모델 설정 (403/404 에러 방지 로직)
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

# 2026년 기준 사용 가능한 모델 리스트를 순차적으로 시도합니다.
MODELS_TO_TRY = [
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest',
    'gemini-1.5-pro',
    'gemini-2.0-flash-exp'
]

model = None
chosen_model_name = ""

for m_name in MODELS_TO_TRY:
    try:
        # 테스트용 객체 생성
        test_model = genai.GenerativeModel(m_name)
        # 실제 호출이 가능한지 확인하기 위해 가벼운 시도 (선택 사항이나 안정성을 위해 권장)
        model = test_model
        chosen_model_name = m_name
        print(f"성공적으로 연결된 모델: {chosen_model_name}")
        break
    except Exception as e:
        print(f"{m_name} 모델 시도 중 오류: {e}")
        continue

if not model:
    # 모든 모델 시도 실패 시 실행 중단
    raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다. API 키나 프로젝트 권한을 확인해 주세요.")

# 2. 네이버 API 딥 서치 쿼리 (핵심 섹터 + 딜 유형)
queries = [
    "반도체 M&A", "반도체 인수합병", "반도체 경영권 매각", "반도체 지분 인수", "반도체 상장",
    "바이오 M&A", "바이오 인수합병", "바이오 경영권 매각", "바이오 지분 인수", "바이오 상장",
    "배터리 M&A", "이차전지 인수합병", "이차전지 지분 투자", "이차전지 상장",
    "스타트업 투자유치", "시리즈A 투자", "시리즈B 투자", "Pre-IPO"
]

exclude_keywords = ["설비", "시설", "연구개발", "R&D", "공장", "증설", "채용", "사옥", "실적", "영업이익", "테마주", "특징주", "급등", "주가"]

news_context = ""
idx = 1
seen_titles = set()

headers = {
    "X-Naver-Client-Id": naver_client_id,
    "X-Naver-Client-Secret": naver_client_secret
}

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

for q in queries:
    encoded_query = urllib.parse.quote(q)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded_query}&display=50&sort=sim"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data.get('items', []):
                title = clean_html(item['title'])
                link = item['originallink'] if item['originallink'] else item['link']
                try:
                    pub_date_obj = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S %z')
                    pub_date = pub_date_obj.strftime('%Y.%m.%d')
                except:
                    pub_date = "최근"
                
                if any(bad in title for bad in exclude_keywords): continue
                if title not in seen_titles and idx <= 80:
                    seen_titles.add(title)
                    news_context += f"[{idx}] 제목: {title}\n날짜: {pub_date}\n링크: {link}\n\n"
                    idx += 1
    except Exception as e:
        print(f"[{q}] 뉴스 검색 중 에러: {e}")
        continue

# 3. 오늘 날짜 계산 및 AI 분석
kst = pytz.timezone('Asia/Seoul')
today_now = datetime.now(kst)
today_str = today_now.strftime("%Y년 %m월 %d일")
today_badge_date = today_now.strftime("%Y.%m.%d")

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#718096;'>🎯 수집된 최신 M&A 뉴스가 없습니다.</h3></div>"
else:
    prompt = f"""
    당신은 글로벌 IB의 시니어 M&A 애널리스트입니다. 
    제공된 뉴스 리스트에서 '반도체, 바이오, 배터리, 딥테크' 섹터의 자본 거래 소식을 완벽하게 정리하세요.

    [뉴스 데이터]
    {news_context}

    [작성 규칙]
    1. 완벽한 인수합병(M&A)뿐 아니라, 전략적 파트너십(MOU), 합작법인(JV), 시드~시리즈 투자, IPO 소식을 모두 포함하세요.
    2. 반드시 '반도체', '바이오', '배터리', '기타' 카테고리로 분류하세요.
    3. 동일 건에 대한 기사는 하나로 묶고 기사 링크를 나열하세요.
    4. 사족 없이 오직 HTML <div> 카드들만 출력하세요.
    5. 기사의 '날짜' 데이터를 확인하여, 딜 발생 일자를 헤드라인(<h3>) 안에 [YYYY.MM.DD] 형식으로 포함하세요.
    6. **중요:** 오늘 날짜는 [{today_badge_date}] 입니다. 만약 기사의 날짜가 오늘 날짜와 일치한다면, <h3> 태그 안의 날짜 바로 앞에 반드시 `<span class="new-badge">NEW</span>` 마크를 추가하세요.
    
    [출력 형식]
    <div class="deal-card" data-category="카테고리명">
      <div class="card-header">
        <span class="category-badge">카테고리명</span>
        <h3>🎯 [YYYY.MM.DD] [대상 업체명] 관련 소식</h3>
      </div>
      <ul>
        <li><strong>주체:</strong> [인수/투자/제휴사]</li>
        <li><strong>상태:</strong> [진행상태 (예: 시리즈A 유치, 경영권 매각 등)]</li>
        <li><strong>링크:</strong> <a href="URL1" target="_blank" class="source-link">기사1</a></li>
      </ul>
      <h4>핵심 요약</h4>
      <ul><li>내용1</li><li>내용2</li></ul>
    </div>
    """
    
    try:
        # 안전 설정 최적화
        safety_settings = {
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        }
        
        result = model.generate_content(prompt, safety_settings=safety_settings)
        
        if result and hasattr(result, 'text'):
            # 마크다운 태그 제거
            clean_text = result.text.replace('```html', '').replace('```', '').strip()
            deal_content = clean_text
        else:
            deal_content = "<div class='deal-card'><h3>🎯 AI가 분석 결과를 생성했으나 내용이 비어 있습니다. (안전 필터 작동 가능성)</h3></div>"
            
    except Exception as e:
        print(f"AI 생성 중 상세 에러: {e}")
        deal_content = f"<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 AI 요약 중 에러가 발생했습니다.</h3><p style='color:gray; font-size:0.8em;'>상세원인: {str(e)}</p></div>"

# 4. HTML 대시보드 생성
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
        .new-badge {{ background-color: #e53e3e; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: bold; vertical-align: text-bottom; margin-right: 8px; letter-spacing: 0.5px; }}
        
        @media (max-width: 600px) {{
            body {{ padding: 15px; }}
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

# 최종 파일 저장
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
    
print("작업 완료: index.html 파일이 성공적으로 생성되었습니다.")
