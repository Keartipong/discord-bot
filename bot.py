import time
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
import socket
import aiohttp
import requests
from aiohttp import web
import threading

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

ALLOWED_CHANNELS = ['bot', 'test_bot']

# HTTP Server สำหรับ Render
async def handle_root(request):
    """แสดงสถานะบอท"""
    bot_status = "🟢 Online" if bot.is_ready() else "🔴 Offline"
    guild_count = len(bot.guilds) if bot.guilds else 0
    user_count = len(bot.users) if bot.users else 0
    
    html = f"""
    <html>
    <head>
        <title>Discord Bot Status</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: white; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .status {{ padding: 20px; border-radius: 10px; background: #36393f; margin: 20px 0; }}
            .online {{ border-left: 5px solid #43b581; }}
            .offline {{ border-left: 5px solid #f04747; }}
            .stat {{ display: flex; justify-content: space-between; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Discord Bot Status</h1>
            <div class="status {'online' if bot.is_ready() else 'offline'}">
                <h2>Bot Status: {bot_status}</h2>
                <div class="stat">
                    <span>Bot Name:</span>
                    <span>{bot.user.name if bot.user else 'Unknown'}</span>
                </div>
                <div class="stat">
                    <span>Servers:</span>
                    <span>{guild_count}</span>
                </div>
                <div class="stat">
                    <span>Users:</span>
                    <span>{user_count}</span>
                </div>
                <div class="stat">
                    <span>Latency:</span>
                    <span>{round(bot.latency * 1000)}ms</span>
                </div>
                <div class="stat">
                    <span>Uptime:</span>
                    <span>{time.strftime('%Y-%m-%d %H:%M:%S')}</span>
                </div>
            </div>
            <p>✅ Bot is running and ready to serve!</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def handle_health(request):
    """Health check endpoint"""
    return web.json_response({
        'status': 'healthy',
        'bot_ready': bot.is_ready(),
        'guild_count': len(bot.guilds) if bot.guilds else 0,
        'latency': round(bot.latency * 1000) if bot.latency else 0
    })

async def start_web_server():
    """เริ่มต้น HTTP server"""
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    
    # ใช้พอร์ตจาก environment variable หรือใช้ 10000 เป็นค่าเริ่มต้น
    port = int(os.environ.get('PORT', 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"🌐 HTTP server started on port {port}")
    print(f"📊 Status page: http://localhost:{port}/")
    print(f"🏥 Health check: http://localhost:{port}/health")

def is_allowed_channel():
    """ตรวจสอบว่าเป็นห้องที่อนุญาตหรือไม่"""
    async def predicate(ctx):
        if ctx.guild is None:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")
            return False
        
        if ctx.channel.name.lower() not in [ch.lower() for ch in ALLOWED_CHANNELS]:
            allowed_channels_str = ", ".join([f"#{ch}" for ch in ALLOWED_CHANNELS])
            await ctx.send(f"❌ คำสั่งนี้ใช้ได้เฉพาะในห้อง: {allowed_channels_str}")
            return False
        
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')
    print('------')
    
    for guild in bot.guilds:
        for channel_name in ALLOWED_CHANNELS:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                await channel.send("✅ Bot is now online!")
                break 

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "kuy" in message.content.lower():
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} - don't say harsh words.", delete_after=5)
        except discord.errors.NotFound:
            pass
        except discord.errors.Forbidden:
            await message.channel.send(f"{message.author.mention} - don't say harsh words.", delete_after=5)
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    try:
        await member.send(f"Welcome to the server {member.guild}!")
    except discord.errors.Forbidden:
        pass
    
    channel = discord.utils.get(member.guild.text_channels, name='welcome')
    if channel:
        await channel.send(f"ยินดีต้อนรับ {member.mention} เข้าสู่เซิร์ฟเวอร์! ของโอย่า")

@bot.event
async def on_command_error(ctx, error):
    """จัดการ error ทั่วไป"""
    if isinstance(error, commands.CheckFailure):
        return
    elif isinstance(error, commands.CommandNotFound):
        if ctx.guild and ctx.channel.name.lower() in [ch.lower() for ch in ALLOWED_CHANNELS]:
            await ctx.send("❌ Command not found.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument.", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument.", delete_after=5)
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ Command on cooldown. Try again in {error.retry_after:.1f}s", delete_after=5)
    else:
        logging.error(f"Unexpected error: {error}")
        await ctx.send("❌ An unexpected error occurred.", delete_after=5)

@bot.event
async def on_voice_state_update(member, before, after):
    """จัดการเมื่อมีการเปลี่ยนแปลงใน voice channel"""
    if member == bot.user:
        return
    
    voice_client = member.guild.voice_client
    if voice_client and voice_client.channel:
        members_in_channel = [m for m in voice_client.channel.members if not m.bot]
        if len(members_in_channel) == 0:
            await asyncio.sleep(5)
            members_in_channel = [m for m in voice_client.channel.members if not m.bot]
            if len(members_in_channel) == 0:
                await voice_client.disconnect()

# ============ คำสั่งต่างๆ ที่จำกัดห้อง ============

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 10, commands.BucketType.guild)
async def nettest(ctx):
    """ทดสอบการเชื่อมต่อเครือข่าย"""
    embed = discord.Embed(title="🌐 Network Diagnostic", color=0x0099ff)
    
    start_time = time.time()
    try:
        socket.gethostbyname('discord.com')
        dns_time = round((time.time() - start_time) * 1000)
        embed.add_field(name="🔍 DNS Resolution", value=f"✅ {dns_time}ms", inline=True)
    except Exception as e:
        embed.add_field(name="🔍 DNS Resolution", value="❌ Failed", inline=True)
        dns_time = 999
    
    start_time = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://discord.com/api/v10/gateway') as resp:
                if resp.status == 200:
                    http_time = round((time.time() - start_time) * 1000)
                    embed.add_field(name="🌐 HTTP Connection", value=f"✅ {http_time}ms", inline=True)
                else:
                    embed.add_field(name="🌐 HTTP Connection", value=f"❌ Status: {resp.status}", inline=True)
                    http_time = 999
    except Exception as e:
        embed.add_field(name="🌐 HTTP Connection", value="❌ Failed", inline=True)
        http_time = 999
    
    ws_latency = round(bot.latency * 1000)
    embed.add_field(name="📡 WebSocket", value=f"{ws_latency}ms", inline=True)
    
    suggestions = []
    if dns_time > 100:
        suggestions.append("• เปลี่ยน DNS เป็น 1.1.1.1")
    if http_time > 200:
        suggestions.append("• ตรวจสอบ Firewall/Antivirus")
    if ws_latency > 200:
        suggestions.append("• ปิดโปรแกรมที่ใช้เน็ตมาก")
        suggestions.append("• ตรวจสอบ VPN/Proxy")
    
    if suggestions:
        embed.add_field(name="💡 Suggestions", value="\n".join(suggestions), inline=False)
    
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 30, commands.BucketType.guild)
async def speedtest(ctx):
    """ทดสอบความเร็วการตอบสนองคำสั่ง"""
    results = []
    
    message = await ctx.send("🔄 Testing command response speed...")
    
    for i in range(5):
        start_time = time.time()
        await asyncio.sleep(0.1)
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000)
        results.append(response_time)
        
        await message.edit(content=f"🔄 Testing... {i+1}/5")
        await asyncio.sleep(0.5)
    
    avg_time = sum(results) / len(results)
    min_time = min(results)
    max_time = max(results)
    
    embed = discord.Embed(title="⚡ Speed Test Results", color=0x00ff88)
    embed.add_field(name="📊 Average", value=f"{avg_time:.1f}ms", inline=True)
    embed.add_field(name="🟢 Best", value=f"{min_time}ms", inline=True)
    embed.add_field(name="🔴 Worst", value=f"{max_time}ms", inline=True)
    
    if avg_time < 50:
        rating = "🟢 Excellent"
    elif avg_time < 100:
        rating = "🟡 Good"
    elif avg_time < 200:
        rating = "🟠 Fair"
    else:
        rating = "🔴 Poor"
    
    embed.add_field(name="📈 Rating", value=rating, inline=False)
    embed.add_field(name="📋 Raw Results", value=" | ".join([f"{r}ms" for r in results]), inline=False)
    
    await message.edit(content="", embed=embed)

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 5, commands.BucketType.user)
async def assign(ctx):
    role_name = "test bot"
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role:
        try:
            await ctx.author.add_roles(role)
            await ctx.send(f"{ctx.author.mention} has been assigned the role {role_name}.", delete_after=10)
        except discord.errors.Forbidden:
            await ctx.send(f"❌ I don't have permission to assign roles.", delete_after=5)
    else:
        await ctx.send(f"Role {role_name} not found in this server.", delete_after=5)

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 3, commands.BucketType.user)
async def myroles(ctx):
    roles = [role.name for role in ctx.author.roles if role.name != "@everyone"]
    if roles:
        await ctx.send(f"{ctx.author.mention}, your roles: {', '.join(roles)}", delete_after=15)
    else:
        await ctx.send(f"{ctx.author.mention}, you have no roles.", delete_after=10)

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 3, commands.BucketType.user)
async def ping(ctx):
    """ตรวจสอบ latency ของบอท"""
    start_time = time.time()
    
    message = await ctx.send("🏓 Calculating ping...")
    
    end_time = time.time()
    
    websocket_latency = round(bot.latency * 1000) 
    api_latency = round((end_time - start_time) * 1000) 
    embed = discord.Embed(
        title="🏓 Pong!",
        color=0x00ff88 if websocket_latency < 100 else 0xffaa00 if websocket_latency < 200 else 0xff0000
    )
    
    embed.add_field(
        name="📡 WebSocket Latency",
        value=f"`{websocket_latency}ms`",
        inline=True
    )
    
    embed.add_field(
        name="🔄 API Latency",
        value=f"`{api_latency}ms`",
        inline=True
    )
    
    if websocket_latency < 50:
        status = "🟢 Excellent"
    elif websocket_latency < 100:
        status = "🟡 Good"
    elif websocket_latency < 200:
        status = "🟠 Fair"
    else:
        status = "🔴 Poor"
    
    embed.add_field(
        name="📊 Connection Quality",
        value=status,
        inline=False
    )
    
    if websocket_latency > 150:
        embed.add_field(
            name="💡 Tips",
            value="• ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต\n• ปิดโปรแกรมที่ใช้เน็ตมาก",
            inline=False
        )
    
    embed.timestamp = discord.utils.utcnow()
    
    await message.edit(content="", embed=embed)

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 10, commands.BucketType.user)
async def serverstatus(ctx):
    """ตรวจสอบสถานะเซิร์ฟเวอร์และการเชื่อมต่อ"""
    embed = discord.Embed(
        title="🌐 Server Status",
        color=0x0099ff,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="🤖 Bot Information",
        value=f"**Servers:** {len(bot.guilds)}\n**Users:** {len(bot.users)}\n**Channels:** {sum(len(guild.channels) for guild in bot.guilds)}",
        inline=True
    )
    
    latency = round(bot.latency * 1000)
    embed.add_field(
        name="📡 Connection",
        value=f"**Latency:** {latency}ms\n**Shard:** {bot.shard_id or 'N/A'}\n**Status:** {'🟢 Online' if bot.is_ready() else '🔴 Offline'}",
        inline=True
    )
    
    if ctx.guild and hasattr(ctx.guild, 'region'):
        embed.add_field(
            name="🌍 Guild Region",
            value=f"**Region:** {ctx.guild.region}",
            inline=True
        )
    
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        embed.add_field(
            name="💾 Memory Usage",
            value=f"{memory_mb:.1f} MB",
            inline=True
        )
    except ImportError:
        pass
    
    embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    
    await ctx.send(embed=embed)

@bot.command(name='help')
@is_allowed_channel()
@commands.cooldown(1, 10, commands.BucketType.user)
async def help_command(ctx):
    """แสดงคำสั่งทั้งหมดที่มีอยู่"""
    embed = discord.Embed(
        title="🤖 Bot Commands Help",
        description="รายการคำสั่งทั้งหมดที่สามารถใช้ได้",
        color=0x00ff88
    )
    
    # แสดงห้องที่อนุญาต
    allowed_channels_str = ", ".join([f"#{ch}" for ch in ALLOWED_CHANNELS])
    embed.add_field(
        name="📍 ห้องที่อนุญาต",
        value=f"คำสั่งทั้งหมดใช้ได้เฉพาะในห้อง: {allowed_channels_str}",
        inline=False
    )
    
    # คำสั่งทั่วไป
    embed.add_field(
        name="📋 คำสั่งทั่วไป",
        value=(
            "**!ping** - ตรวจสอบ latency\n"
            "**!assign** - รับ role 'test bot'\n"
            "**!myroles** - ดู roles ของคุณ\n"
            "**!serverstatus** - ดูสถานะเซิร์ฟเวอร์\n"
            "**!help** - แสดงคำสั่งทั้งหมด"
        ),
        inline=False
    )
    
    # คำสั่งทดสอบเครือข่าย
    embed.add_field(
        name="🌐 คำสั่งทดสอบเครือข่าย",
        value=(
            "**!nettest** - ทดสอบการเชื่อมต่อเครือข่าย\n"
            "**!speedtest** - ทดสอบความเร็วการตอบสนอง"
        ),
        inline=False
    )
    embed.add_field(
        name="📍🎵  ห้องที่อนุญาต",
        value=f"คำสั่งทั้งหมดใช้ได้เฉพาะในห้อง: music-bot",
        inline=False
    )
    # คำสั่งเพลง
    embed.add_field(
        name="🎵 คำสั่งเพลง",
        value=(
            "**!join** - ให้บอทเข้า voice channel\n"
            "**!leave** - ให้บอทออกจาก voice channel\n"
            "**!play <url/คำค้นหา>** - เล่นเพลงจาก YouTube\n"
            "**!stop** - หยุดเล่นเพลง\n"
            "**!pause** - หยุดเพลงชั่วคราว\n"
            "**!resume** - เล่นเพลงต่อ\n"
            "**!volume <0-100>** - ปรับระดับเสียง\n"
            "**!status** - ดูสถานะบอท"
        ),
        inline=False
    )
    
    # ข้อมูลเพิ่มเติม
    embed.add_field(
        name="ℹ️ ข้อมูลเพิ่มเติม",
        value=(
            "• บอทจะลบข้อความที่มีคำว่า 'kuy' ในทุกห้อง\n"
            "• บอทจะต้อนรับสมาชิกใหม่อัตโนมัติ\n"
            "• บอทจะออกจาก voice channel เมื่อไม่มีคนฟัง\n"
            "• สำหรับเพลง: ใส่ URL หรือชื่อเพลงก็ได้"
        ),
        inline=False
    )
    
    embed.set_footer(text="🔥 Made with ❤️ | Prefix: !")
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    await ctx.send(embed=embed)

@bot.command()
@is_allowed_channel()
@commands.cooldown(1, 10, commands.BucketType.user)
async def channels(ctx):
    """แสดงรายการห้องที่อนุญาตให้ใช้คำสั่ง"""
    embed = discord.Embed(
        title="📍 Allowed Channels",
        description="ห้องที่สามารถใช้คำสั่งบอทได้",
        color=0x00ff88
    )
    
    # หาห้องที่มีอยู่จริงในเซิร์ฟเวอร์
    existing_channels = []
    missing_channels = []
    
    for channel_name in ALLOWED_CHANNELS:
        channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
        if channel:
            existing_channels.append(f"✅ {channel.mention}")
        else:
            missing_channels.append(f"❌ #{channel_name}")
    
    if existing_channels:
        embed.add_field(
            name="🟢 ห้องที่ใช้ได้",
            value="\n".join(existing_channels),
            inline=False
        )
    
    if missing_channels:
        embed.add_field(
            name="🔴 ห้องที่ไม่พบ",
            value="\n".join(missing_channels),
            inline=False
        )
    
    embed.add_field(
        name="💡 หมายเหตุ",
        value="คำสั่งทั้งหมดจะทำงานเฉพาะในห้องที่แสดงด้านบนเท่านั้น",
        inline=False
    )
    
    await ctx.send(embed=embed)

async def load_cogs():
    """โหลด cogs"""
    try:
        await bot.load_extension("music_commands")
        print("✅ Music commands loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load music commands: {e}")

# AI Command
@bot.command()
async def chat(ctx, *, prompt):
    """คุยกับ AI (DeepInfra)"""
    async with ctx.typing():
        try:
            url = "https://api.deepinfra.com/v1/openai/chat/completions"
            headers = {
                "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.7
            }
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()
            print(result)

            if "choices" in result and result["choices"]:
                answer = result["choices"][0]["message"]["content"]
                await ctx.send(answer)
            else:
                error_msg = result.get("error", result)
                await ctx.send(f"เกิดข้อผิดพลาดจาก DeepInfra: {error_msg}")
        except Exception as e:
            await ctx.send(f"เกิดข้อผิดพลาด: {e}")

async def main():
    """ฟังก์ชันหลักในการรันบอท"""
    if token is None:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        return
    
    print(f"🎯 Bot will only respond to commands in channels: {', '.join(ALLOWED_CHANNELS)}")
    
    # เริ่มต้น HTTP server
    await start_web_server()
    
    async with bot:
        await load_cogs()
        try:
            await bot.start(token)
        except discord.errors.LoginFailure:
            print("❌ Invalid token provided.")
        except Exception as e:
            print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())