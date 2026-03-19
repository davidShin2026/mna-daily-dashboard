import os
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
from datetime import datetime
import pytz

# 1. API 키 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# 2. 타겟 섹터 M&A 뉴스 수집
query = "M&A OR 인수 OR 합병 (Vision AI OR 실리콘 포토닉스 OR 전고체 배터리 OR 데이터센터)"
rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

response = requests.get(rss_url)
root = ET.fromstring(response.text)

news_context = ""
for i, item in enumerate(root.findall('.//item')[:5]):
    title = item.find('title').text
    link = item.find('link').text
    news_context += f"{i+1}. 제목: {title}\n링크: {link}\n\n"

if not news_context.strip():
    deal_content = "<div class='deal-card'><h3>오늘의 M&A 소식이 없습니다.</h3></div>"
else:
    # 3. Gemini API 프롬프트 세팅
    prompt = f"""
    당신은 글로벌 IB의 탑티어 M&A 리서치 애널리스트입니다. 
    아래 뉴스를 바탕으로 지난 24시간 동안 발생한 주요 M&A 및 지분 투자 소식을 요약해 주세요.

    [뉴스 데이터]
    {news_context}

    [필수 조건]
    1. 누락 불가: 인수 주체와 매각 대상의 사명 명시.
    2. 딜 세부 정보: 거래 대상 지분 규모, 지분율, 금액 포함 (확인 불가 시 '미상' 표기).
    3. 사업 개요: 대상 업체의 핵심 비즈니스를 3줄 이내 개조식 요약.
    4. 재무 정보: 최근 3개년 매출액, 영업이익, 당기순이익 표 작성.

    [출력 형식 (반드시 아래 HTML 태그만 출력할 것)]
    <div class="deal-card">
      <h3>🎯 [대상 업체명] M&A 건</h3>
      <ul>
        <li><strong>인수 주체:</strong> [인수 업체명]</li>
        <li><strong>매각 대상:</strong> [피인수 업체명]</li>
        <li><strong>딜 규모:</strong> [인수 금액] / 지분 [지분율]% 확보</li>
      </ul>
      <h4>사업 개요</h4>
      <ul><li>[내용 1]</li><li>[내용 2]</li><li>[내용 3]</li></ul>
      <h4>최근 3개년 재무 현황</h4>
      <table>
        <tr><th>연도</th><th>매출액</th><th>영업이익</th><th>당기순이익</th></tr>
        <tr><td>2023</td><td>-</td><td>-</td><td>-</td></tr>
      </table>
    </div>
    """

    model = genai.GenerativeModel('gemini-pro')
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
