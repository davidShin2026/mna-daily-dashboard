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

# 2. (핵심 수정) 국내 한정 + 기간 넉넉히(1년) + URL 안전 인코딩
query = "국내 (인수합병 OR 지분투자 OR 매각 OR 경영권) (반도체 OR 바이오 OR 제약 OR 헬스케어 OR 배터리 OR 2차전지) when:1y"
encoded_query = urllib.parse.quote(query) # 구글이 검색어를 100% 인식하도록 인코딩
rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

response = requests.get(rss_url)
root = ET.fromstring(response.text)

news_context = ""
for i, item in enumerate(root.findall('.//item')[:30]):
    title = item.find('title').text
    link = item.find('link').text
    pubDate = item.find('pubDate').text if item.find('pubDate') is not None else '날짜 미상'
    news_context += f"{i+1}. 제목: {title}\n일자: {pubDate}\n링크: {link}\n\n"

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 뉴스 검색 결과가 없습니다.</h3></div>"
else:
    # 3. (핵심 수정) AI의 깐깐함 완화 - '추진/검토/MOU' 모두 포함 지시
    prompt = f"""
    당신은 글로벌 IB의 탑티어 M&A 리서치 애널리스트입니다. 
    아래 뉴스를 바탕으로 국내 핵심 섹터의 M&A 및 지분 투자 동향을 요약해 주세요.

    [뉴스 데이터]
    {news_context}

    [필수 조건]
    1. 완벽히 확정된 딜이 아니더라도, '인수 추진', '매각 검토', '투자 유치', 'MOU 체결' 등 M&A/투자와 관련된 진행 중인 사안이라면 무조건 포함하세요.
    2. 발견된 유의미한 소식이 여러 개라면, 아래 [출력 형식 1]의 HTML <div> 태그 블록을 소식의 개수만큼 반복해서 모두 출력하세요.
    3. 만약 눈을 씻고 찾아봐도 관련된 기업 소식이 단 하나도 없다면, 오직 [출력 형식 2]의 HTML 태그 하나만 출력하세요.

    [출력 형식 1 (관련 딜/썰이 있을 때 - 개수만큼 반복 출력)]
    <div class="deal-card">
      <h3>🎯 [대상 업체명] M&A/투자 동향</h3>
      <ul>
        <li><strong>관련 주체:</strong> [인수/투자/매각 관련 업체명]</li>
        <li><strong>진행 상태:</strong> [예: 인수 확정 / 매각 검토 중 / 투자 유치 중 등]</li>
        <li><strong>예상 규모:</strong> [금액 또는 미상]</li>
      </ul>
      <h4>주요 내용 요약</h4>
      <ul><li>[기사 핵심 내용 1]</li><li>[기사 핵심 내용 2]</li></ul>
    </div>

    [출력 형식 2 (관련 소식이 전혀 없을 때)]
    <div class="deal-card">
      <h3 style="color:#e53e3e;">🎯 확인된 주요 M&A 딜 없음</h3>
      <p>수집된 뉴스 중 유의미한 인수합병 및 지분 투자 소식이 없습니다.</p>
    </div>
    """

    model = genai.GenerativeModel(chosen_model_name.replace('models/', ''))
    result = model.generate_content(prompt)
    deal_content = result.text

# 4. HTML 파일 생성
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
        h1 {{ color: #1a365d; text-align: center; }}
        .date {{ text-align: center; color: #718096; margin-bottom: 30px; font-weight: bold; }}
        .deal-card {{ background: #fff; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 5px solid #2b6cb0; margin-bottom: 20px; }}
        .deal-card h3 {{ color: #2b6cb0; border-bottom: 2px solid #edf2f7; padding-bottom: 10px; margin-top: 0; }}
        ul {{ line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Domestic M&A Daily Dashboard</h1>
        <div class="date">업데이트: {today_str} 오전 8:10</div>
        {deal_content}
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
