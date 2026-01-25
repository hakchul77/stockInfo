import discord
from discord.ext import commands
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from bot_config import settings

# 디스코드 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def safe_float(value):
    try:
        # 빈 문자열이나 특수문자 제거 후 변환
        clean_value = str(value).replace(',', '').strip()
        return float(clean_value)
    except (ValueError, TypeError):
        return None  # 변환 실패 시 None 반환
    
def safe_convert(value):
    """Clean string data and convert to float safely."""
    if value is None or value == '' or '-' in str(value) or 'N/A' in str(value):
        return None
    try:
        # Remove commas and extract numeric parts
        clean_val = "".join(c for c in str(value) if c.isdigit() or c == '.' or c == '-')
        return float(clean_val)
    except ValueError:
        return None    

def get_financial_data(code):
    """네이버 증권에서 주요 재무 지표를 크롤링합니다."""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    metrics = {}
    try:
        # 네이버 증권의 주요재무정보 테이블(표)을 찾습니다.
        table = soup.select_one(".section.cop_analysis div.sub_section table")
        # 항목들 추출 (ROE, 부채비율, PSR 계산을 위한 매출액 등)
        # 실제 운영시에는 행/열 인덱스를 정교하게 매칭해야 합니다.
        rows = table.select("tbody tr")
        
        # 현재주가, 시가총액, 증거금률, 52주 최저가, 52주 최고가,
        # PER, PBR, PSR, PCR, PEG, ROE, ROA
        # 영업이익률, 순이익률, 매출액 증가율, 순이익 증가율, 부채비율, 유동비율, 유보율, 배당수익률, 외국인 지분율

        # --- Market Info ---
        metrics['current_price'] = safe_convert(soup.select_one(".no_today .blind").text)
        metrics['market_cap'] = safe_convert(soup.select_one("#_market_sum").text.replace("조", "").replace("억원", ""))
        
        # 52-week High/Low
        week_52_data = soup.select(".tab_con1 .blind")
        metrics['week_52_low'] = safe_convert(week_52_data[0].text) if len(week_52_data) > 0 else None
        metrics['week_52_high'] = safe_convert(week_52_data[1].text) if len(week_52_data) > 1 else None
        
        # Foreign Ownership
        foreign_el = soup.select_one(".gray .lft th:contains('외국인소진율') + td")
        metrics['foreign_ratio'] = safe_convert(foreign_el.text) if foreign_el else None

        # --- Financial Analysis (cop_analysis table) ---
        table = soup.select_one(".section.cop_analysis div.sub_section table")
        rows = table.select("tbody tr")
        
        # Mapping by row index (Based on Naver Finance standard layout)
        # Column [3] usually represents the latest annual data
        metrics['sales'] = safe_convert(rows[0].select("td")[3].text)
        metrics['operating_profit_margin'] = safe_convert(rows[1].select("td")[3].text)
        metrics['net_profit_margin'] = safe_convert(rows[2].select("td")[3].text)
        metrics['roe'] = safe_convert(rows[5].select("td")[3].text)
        metrics['debt_ratio'] = safe_convert(rows[6].select("td")[3].text)
        metrics['current_ratio'] = safe_convert(rows[7].select("td")[3].text)
        metrics['reserve_ratio'] = safe_convert(rows[8].select("td")[3].text)
        metrics['per'] = safe_convert(rows[10].select("td")[3].text)
        metrics['pbr'] = safe_convert(rows[12].select("td")[3].text)
        metrics['dividend_yield'] = safe_convert(rows[13].select("td")[3].text)

        # data['sales'] = rows[0].select("td")[3].text.strip().replace(',', '') # 최근 매출액
        # data['roe'] = rows[5].select("td")[3].text.strip().replace(',', '')
        # data['debt_ratio'] = rows[6].select("td")[3].text.strip().replace(',', '')
        # data['eps'] = rows[9].select("td")[3].text.strip().replace(',', '')
        # data['per'] = rows[10].select("td")[3].text.strip().replace(',', '')
        # data['bps'] = rows[11].select("td")[3].text.strip().replace(',', '')
        # data['pbr'] = rows[12].select("td")[3].text.strip().replace(',', '')

        # --- Calculated Metrics ---
        # PSR = Market Cap / Sales
        if metrics['market_cap'] and metrics['sales']:
            metrics['psr'] = round(metrics['market_cap'] / metrics['sales'], 2)
        else:
            metrics['psr'] = None

        # ROA / PCR / PEG / Sales Growth / Profit Growth
        # Note: These may require cross-referencing previous year data for growth rates.
        # For now, setting placeholder or simplified logic.
        metrics['roa'] = None  # Requires 'Financials' tab for precision
        metrics['pcr'] = None
        metrics['peg'] = None
        metrics['sales_growth'] = None
        metrics['profit_growth'] = None
        metrics['margin_rate'] = None # Example: Margin requirement (brokerage specific)
    except Exception as e:
        print(f"데이터 추출 중 오류: {e}")
    return metrics

@bot.command()
async def 조회(ctx, name):
    await ctx.send(f"🔍 '{name}' 종목의 21개 항목을 정밀 분석 중입니다...")

    # 1. 기초 데이터 로드
    df_krx = fdr.StockListing('KRX')
    target = df_krx[df_krx['Name'] == name]
    
    if target.empty:
        await ctx.send(f"❌ '{name}' 종목을 찾을 수 없습니다.")
        return

    # 데이터 타입 에러 방지를 위해 숫자로 변환
    code = target.iloc[0]['Code']
    price = int(target.iloc[0]['Close'])
    m_cap = int(target.iloc[0]['Marcap'] / 10**8) # 억 단위
    
    # 실시간 크롤링 실행
    fin_data = get_financial_data(code)

    # PSR 직접 계산 (시가총액 / 매출액)
    try:
        sales = int(fin_data.get('sales', 0)) * 10**8 # 네이버는 억원 단위
        psr = round(m_cap / (sales / 10**8), 2) if sales > 0 else "N/A"
    except:
        psr = "N/A"

    roe = fin_data.get('roe', 'N/A')
    debt_raw = fin_data.get('debt_ratio', 'N/A')
    debt_val = safe_float(debt_raw) # 안전하게 숫자화

    # 결과 출력 시 조건 검사
    if debt_val is not None:
        debt_status = '✅' if debt_val <= 100 else '❌'
        debt_display = f"{debt_val}%"
    else:
        debt_status = '⚠️ 점검필요'
        debt_display = '데이터 없음'

    # 디스코드 카드 생성
    embed = discord.Embed(title=f"🚀 {name} ({code}) 실시간 분석", color=0x3498db)

    # 21개 항목 중 주요 지표 출력
    val_info = f"1. 시가총액: {m_cap:,}억 ({'✅' if m_cap >= 3000 else '❌'})\n"
    val_info += f"7. **PSR: {psr} ({'✅' if psr != 'N/A' and psr <= 0.5 else '❌'})**"
    embed.add_field(name="🔹 밸류에이션", value=val_info, inline=False)

    growth_info = f"10. ROE: {roe}% ({'✅' if roe != 'N/A' and float(roe) >= 5 else '❌'})\n"
    growth_info += f"16. 부채비율: {debt_display} ({debt_status})"
    embed.add_field(name="🔹 수익성 및 안정성", value=growth_info, inline=False)

    embed.set_footer(text="기준: 최근 결산 및 PSR 매수원칙 적용")

    # # 2. 디스코드 임베드 생성 (카드 형식)
    # embed = discord.Embed(
    #     title=f"📈 {name} ({code}) 투자 체크리스트",
    #     description=f"현재 주가: **{price:,}원** | 시가총액: **{m_cap:,}억**",
    #     color=0x00ff00 if m_cap > 3000 else 0xff0000
    # )

    # # 3. 항목별 섹션 추가 (가독성을 위해 그룹화)
    # # 기본 지표 섹션
    # basic_info = (
    #     f"1. 시가총액: {m_cap:,}억 ({'✅' if m_cap >= 3000 else '❌'})\n"
    #     f"5. PER: {target.iloc[0].get('Reading', 'N/A')} ({'점검'}) \n"
    #     f"7. **PSR: {psr} ({'✅' if psr <= 0.5 else '❌ 매수권 아님'})**"
    # )
    # embed.add_field(name="🔹 기본 및 밸류에이션", value=basic_info, inline=False)
    
    # # 안정성 및 수익성 섹션 (예시 수치 적용)
    # stability_info = (
    #     f"10. ROE: 13.3% (✅ 5%↑)\n"
    #     f"16. 부채비율: 11% (✅ 100%↓)\n"
    #     f"17. 유동비율: 214% (✅ 200%↑)"
    # )
    # embed.add_field(name="🔹 재무 건전성", value=stability_info, inline=False)

    # # 투자 등급 안내 (메모 기반)
    # embed.set_footer(text="💡 PSR 0.5 이하 매수 / 3.0 이상 매도 권장")

    await ctx.send(embed=embed)

bot.run(settings.DISCORD_BOT_TOKEN)