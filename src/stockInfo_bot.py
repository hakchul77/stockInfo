import discord
from discord.ext import commands
from bot_config import settings
from supabase import create_client, Client

# 디스코드 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Supabase 클라이언트 설정
try:
    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    print("Supabase 클라이언트가 성공적으로 초기화되었습니다.")
except Exception as e:
    print(f"Supabase 연결 설정 오류: {e}")
    supabase = None

@bot.event
async def on_ready():
    print(f'로그인 성공: {bot.user}')

@bot.command(name="status", aliases=["상태", "현재상태"])
async def status(ctx, stock_name: str = None):
    """
    현재 활성화된 트레이딩 상태를 조회합니다.
    사용법: !status [종목명]
    """
    if not supabase:
        await ctx.send("Supabase 클라이언트가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return

    msg = await ctx.send("Supabase에서 데이터 조회 중...")

    try:
        # 기본 쿼리 생성
        query = supabase.table('trade_tranche') \
            .select('tranche_index, status, target_buy_price, target_sell_price, quantity, updated_at, trade_master!inner(strategy_name, stock_name)') \
            .eq('trade_master.is_active', True) \
            .neq('status', 'READY')

        # 종목명이 입력된 경우 필터 추가 (trade_master의 stock_name 기준)
        if stock_name:
            query = query.ilike('trade_master.stock_name', f'%{stock_name}%')

        # 실행
        response = query.order('master_id') \
            .order('tranche_index') \
            .execute()
        
        data = response.data
        if not data:
            if stock_name:
                await msg.edit(content=f"'{stock_name}'에 대한 조회된 데이터가 없습니다.")
            else:
                await msg.edit(content="조회된 데이터가 없습니다.")
            return

        title = f"현재 트레이딩 상태 ({stock_name})" if stock_name else "현재 트레이딩 상태 (전체)"
        embed = discord.Embed(title=title, color=0x3498db)
        
        for item in data:
            master = item.get('trade_master', {})
            s_name = master.get('stock_name', 'Unknown')
            strategy_name = master.get('strategy_name', 'Unknown')
            
            idx = item.get('tranche_index')
            status_val = item.get('status')
            buy_price = item.get('target_buy_price', 0)
            sell_price = item.get('target_sell_price', 0)
            qty = item.get('quantity', 0)

            # 보기 좋게 포맷팅
            field_name = f"[{strategy_name}] {s_name} (#{idx})"
            field_value = (
                f"Status: {status_val}\n"
                f"Target Buy: {buy_price:,}\n"
                f"Target Sell: {sell_price:,}\n"
                f"Qty: {qty:,}"
            )
            embed.add_field(name=field_name, value=field_value, inline=False)

        embed.set_footer(text=f"Total: {len(data)} items")
        
        await msg.edit(content="", embed=embed)

    except Exception as e:
        await msg.edit(content=f"데이터 조회 중 오류 발생: {e}")

# 봇 실행
if __name__ == "__main__":
    bot.run(settings.DISCORD_BOT_TOKEN)
