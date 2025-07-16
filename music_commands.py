import discord
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# รายชื่อ channel ที่อนุญาตให้ใช้คำสั่ง
ALLOWED_CHANNELS = ['music-bot', 'music', 'bot-commands']

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.guild is None:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")
            return False

        if ctx.channel.name.lower() not in [ch.lower() for ch in ALLOWED_CHANNELS]:
            allowed_channels_str = ", ".join([f"#{ch}" for ch in ALLOWED_CHANNELS])
            await ctx.send(f"❌ คำสั่งนี้ใช้ได้เฉพาะในห้อง: {allowed_channels_str}")
            return False

        return True

    @commands.command()
    async def join(self, ctx):
        """ให้บอทเข้าห้อง voice ที่ผู้ใช้กำลังอยู่"""
        try:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                if ctx.voice_client:
                    await ctx.voice_client.move_to(channel)
                    await ctx.send(f"✅ ย้ายไปยัง: {channel}")
                else:
                    await channel.connect()
                    await ctx.send(f"✅ เข้าร่วมห้อง: {channel}")
            else:
                await ctx.send("❌ คุณไม่ได้อยู่ในห้อง voice")
        except Exception as e:
            logger.error(f"Error joining voice channel: {e}")
            await ctx.send("❌ ไม่สามารถเข้าห้อง voice ได้")

    @commands.command()
    async def leave(self, ctx):
        """ให้บอทออกจากห้อง voice"""
        try:
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                await ctx.send("✅ ออกจากห้อง voice แล้ว")
            else:
                await ctx.send("❌ บอทไม่ได้อยู่ในห้อง voice")
        except Exception as e:
            logger.error(f"Error leaving voice channel: {e}")
            await ctx.send("❌ ไม่สามารถออกจากห้อง voice ได้")

    @commands.command()
    async def play(self, ctx, *, url):
        """เล่นเพลงจาก YouTube (url หรือ keyword)"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ คุณต้องอยู่ในห้อง voice ก่อน")
                return

            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()
                await ctx.send(f"✅ เข้าร่วมห้อง: {ctx.author.voice.channel}")

            search_msg = await ctx.send("🔍 กำลังค้นหา...")

            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'noplaylist': True,
                'default_search': 'ytsearch',
                'extractaudio': True,
                'audioformat': 'opus',
                'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
                'restrictfilenames': True,
                'logtostderr': False,
                'ignoreerrors': False,
                'no_warnings': True,
                'source_address': '0.0.0.0',
                'socket_timeout': 30
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: ydl.extract_info(url, download=False)
                        ),
                        timeout=30
                    )

                    if 'entries' in info:
                        if len(info['entries']) == 0:
                            await search_msg.edit(content="❌ ไม่พบผลการค้นหา")
                            return
                        info = info['entries'][0]

                    audio_url = info.get('url')
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)
                    uploader = info.get('uploader', 'Unknown')

                    if not audio_url:
                        await search_msg.edit(content="❌ ไม่สามารถดึง URL เสียงได้")
                        return

                except asyncio.TimeoutError:
                    await search_msg.edit(content="❌ หมดเวลาในการค้นหา")
                    return
                except Exception as e:
                    logger.error(f"yt-dlp extraction error: {e}")
                    await search_msg.edit(content="❌ ไม่สามารถดึงข้อมูลวิดีโอได้")
                    return

            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn -filter:a "volume=0.5"'
            }

            try:
                if ctx.voice_client.is_playing():
                    ctx.voice_client.stop()

                source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)

                def after_playing(error):
                    if error:
                        logger.error(f'Player error: {error}')
                        asyncio.run_coroutine_threadsafe(
                            ctx.send(f"❌ ข้อผิดพลาดในการเล่น: {error}"),
                            self.bot.loop
                        )
                    else:
                        asyncio.run_coroutine_threadsafe(
                            ctx.send("✅ เล่นเพลงเสร็จสิ้น"),
                            self.bot.loop
                        )

                ctx.voice_client.play(source, after=after_playing)

                duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
                embed = discord.Embed(
                    title="🎵 กำลังเล่น",
                    color=0x00ff00
                )
                embed.add_field(name="เพลง", value=title, inline=False)
                embed.add_field(name="ความยาว", value=duration_str, inline=True)
                embed.add_field(name="ผู้อัปโหลด", value=uploader, inline=True)
                embed.set_footer(text=f"ขอโดย {ctx.author.display_name}")
                
                await search_msg.edit(content="", embed=embed)

            except Exception as e:
                logger.error(f"Playback error: {e}")
                await search_msg.edit(content="❌ ไม่สามารถเล่นเสียงได้")

        except Exception as e:
            logger.error(f"General play command error: {e}")
            await ctx.send("❌ เกิดข้อผิดพลาดที่ไม่คาดคิด")

    @commands.command()
    async def stop(self, ctx):
        """หยุดเล่นเพลง"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏹️ หยุดเล่นเพลงแล้ว")
        else:
            await ctx.send("❌ ไม่มีเพลงที่กำลังเล่นอยู่")

    @commands.command()
    async def pause(self, ctx):
        """หยุดเพลงชั่วคราว"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ หยุดเพลงชั่วคราว")
        else:
            await ctx.send("❌ ไม่มีเพลงที่กำลังเล่นอยู่")

    @commands.command()
    async def resume(self, ctx):
        """เล่นเพลงต่อ"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ เล่นเพลงต่อแล้ว")
        else:
            await ctx.send("❌ ไม่มีเพลงที่หยุดชั่วคราว")

    @commands.command()
    async def volume(self, ctx, volume: int = None):
        """ปรับระดับเสียง (0-100)"""
        if volume is None:
            await ctx.send("❌ กรุณาระบุระดับเสียง (0-100)")
            return

        if not 0 <= volume <= 100:
            await ctx.send("❌ ระดับเสียงต้องอยู่ระหว่าง 0-100")
            return

        if ctx.voice_client and hasattr(ctx.voice_client.source, 'volume'):
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"🔊 ตั้งระดับเสียงเป็น {volume}%")
        else:
            await ctx.send("❌ ไม่มีเสียงที่กำลังเล่นอยู่หรือไม่สามารถปรับเสียงได้")

    @commands.command()
    async def status(self, ctx):
        """แสดงสถานะปัจจุบันของบอท"""
        if not ctx.voice_client:
            await ctx.send("❌ ไม่ได้เชื่อมต่อกับห้อง voice")
            return

        channel = ctx.voice_client.channel
        status = "🔴 ไม่มีอะไร"

        if ctx.voice_client.is_playing():
            status = "🟢 กำลังเล่น"
        elif ctx.voice_client.is_paused():
            status = "🟡 หยุดชั่วคราว"

        embed = discord.Embed(
            title="🤖 สถานะบอท",
            color=0x0099ff
        )
        embed.add_field(name="ห้อง Voice", value=channel.name, inline=True)
        embed.add_field(name="สถานะ", value=status, inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)

        await ctx.send(embed=embed)

    @commands.command()
    async def help_music(self, ctx):
        """แสดงคำสั่งทั้งหมดของ Music Bot"""
        embed = discord.Embed(
            title="🎵 คำสั่ง Music Bot",
            description="คำสั่งสำหรับเล่นเพลงใน Discord",
            color=0x00ff00
        )
        
        commands_list = [
            ("!join", "ให้บอทเข้าห้อง voice"),
            ("!leave", "ให้บอทออกจากห้อง voice"),
            ("!play <เพลง>", "เล่นเพลงจาก YouTube"),
            ("!stop", "หยุดเล่นเพลง"),
            ("!pause", "หยุดเพลงชั่วคราว"),
            ("!resume", "เล่นเพลงต่อ"),
            ("!volume <0-100>", "ปรับระดับเสียง"),
            ("!status", "แสดงสถานะบอท"),
            ("!help_music", "แสดงคำสั่งนี้")
        ]
        
        for command, description in commands_list:
            embed.add_field(name=command, value=description, inline=False)
        
        embed.set_footer(text="ใช้คำสั่งได้เฉพาะในห้อง music-bot เท่านั้น")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))