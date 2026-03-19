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

# 2. (수정됨) 검색어 정밀 타겟팅 ("인수합병", "지분투자" 정확히 매칭)
query = '("인수합병" OR "지분투자" OR "경영권 인수") (반도체 OR 바이오 OR 제약 OR 헬스케어 OR 배터리 OR 이차전지) when:3m'
rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

response = requests.get(rss_url)
root = ET.fromstring(response.text)

news_context = ""
for i, item in enumerate(root.findall('.//item')[:15]):
    title = item.find('title').text
    link = item.find('link').text
    news_context += f"{i+1}. 제목: {title}\n링크: {link}\n\n"

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3 style='color:#e53e3e;'>🎯 조건에 맞는 뉴스가 검색되지 않았습니다.</h3></div>"
else:
    # 3. (수정됨) AI가 절대 줄글을 쓰지 못하도록 강력 통제
    prompt = f"""
    당신은 글로벌 IB의 탑티어 M&A 리서치 애널리스트입니다. 
    아래 뉴스를 바탕으로 '최근 3개월 동안' 발생한 주요 M&A 및 지분 투자 소식을 요약해 주세요.

    [뉴스 데이터]
    {news_context}

    [엄격한 필수 조건]
    1. 제공된 뉴스 중 '실제 기업 간의 인수합병(M&A)' 또는 '지분 투자' 건만 추출하세요. (단순 MOU, 정부 정책, 게임 출시 뉴스는 완벽히 배제할 것)
    2. 추출할 딜이 1개라도 있다면 반드시 [출력 형식 1]의 HTML 태그만 출력하세요.
    3. 만약 진짜 딜 소식이 단 하나도 없다면, 절대 부연 설명이나 사족을 달지 말고 오직 [출력 형식 2]의 HTML 태그만 출력하세요.

    [출력 형식 1 (관련 딜이 있을 때)]
    <div class="deal-card">
      <h3>🎯 [대상 업체명] M&A 건</h3>
      <ul>
        <li><strong>인수 주체:</strong> [인수 업체명]</li>
        <li><strong>매각 대상:</strong> [피인수 업체명]</li>
        <li><strong>딜 규모:</strong> [인수 금액] / 지분 [지분율]% 확보</li>
      </ul>
      <h4>사업 개요</h4>
      <ul><li>[내용 1]</li><li>[내용 2]</li></ul>
      <h4>최근 3개년 재무 현황</h4>
      <table>
        <tr><th>연도</th><th>매출액</th><th>영업이익</th><th>당기순이익</th></tr>
        <tr><td>2023</td><td>-</td><td>-</td><td>-</td></tr>
      </table>
    </div>

    [출력 형식 2 (관련 딜이 없을 때 - 부연 설명 절대 금지)]
    <div class="deal-card">
      <h3 style="color:#e53e3e;">🎯 확인된 주요 M&A 딜 없음</h3>
      <p>최근 3개월 뉴스 중 유의미한 인수합병 및 지분 투자 소식이 없습니다.</p>
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
    <title>Global M&A Daily Dashboard</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px; color: #333; }}
        .container {{ max-width: 900px; margin: auto; }}
        h1 {{ color: #1a365d; text-align: center; }}
        .date {{ text-align: center; color: #718096; margin-bottom: 30px; font-weight: bold; }}
        .deal-card {{ background: #fff; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 5px solid #2b6cb0; margin-bottom: 20px; }}
        .deal-card h3 {{ color: #2b6cb0; border-bottom: 2px solid #edf2f7; padding-bottom: 10px; margin-top: 0; }}
        ul {{ line-height: 1.6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9em; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: right; }}
        th {{ background-color: #f7fafc; text-align: center; color: #4a5568; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Global M&A Daily Dashboard</h1>
        <div class="date">업데이트: {today_str} 오전 8:10</div>
        {deal_content}
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
