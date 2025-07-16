import discord
from discord.ext import commands
import yt_dlp
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# รายชื่อ channel ที่อนุญาตให้ใช้คำสั่ง
ALLOWED_CHANNELS = ['music-bot']

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ✅ ตรวจสอบว่าใช้คำสั่งในห้องที่อนุญาตหรือไม่
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
                    await ctx.send(f"Moved to: {channel}")
                else:
                    await channel.connect()
                    await ctx.send(f"Joined in: {channel}")
            else:
                await ctx.send("You are not in a voice channel.")
        except Exception as e:
            logger.error(f"Error joining voice channel: {e}")
            await ctx.send("Failed to join voice channel.")

    @commands.command()
    async def leave(self, ctx):
        """ให้บอทออกจากห้อง voice"""
        try:
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                await ctx.send("Disconnected.")
            else:
                await ctx.send("I'm not in a voice channel.")
        except Exception as e:
            logger.error(f"Error leaving voice channel: {e}")
            await ctx.send("Failed to leave voice channel.")

    @commands.command()
    async def play(self, ctx, *, url):
        """เล่นเพลงจาก YouTube (url หรือ keyword)"""
        try:
            if not ctx.author.voice:
                await ctx.send("You are not in a voice channel.")
                return

            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()
                await ctx.send(f"Connected to: {ctx.author.voice.channel}")

            search_msg = await ctx.send("🔍 Searching...")

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
                'source_address': '0.0.0.0'
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: ydl.extract_info(url, download=False)
                    )

                    if 'entries' in info:
                        if len(info['entries']) == 0:
                            await search_msg.edit(content="❌ No results found.")
                            return
                        info = info['entries'][0]

                    audio_url = info.get('url')
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)

                    if not audio_url:
                        await search_msg.edit(content="❌ Could not extract audio URL.")
                        return

                except Exception as e:
                    logger.error(f"yt-dlp extraction error: {e}")
                    await search_msg.edit(content="❌ Failed to extract video information.")
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
                            ctx.send(f"❌ Playback error: {error}"),
                            self.bot.loop
                        )
                    else:
                        asyncio.run_coroutine_threadsafe(
                            ctx.send("✅ Playback finished"),
                            self.bot.loop
                        )

                ctx.voice_client.play(source, after=after_playing)

                duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"**{title}**\nDuration: {duration_str}",
                    color=0x00ff00
                )
                await search_msg.edit(content="", embed=embed)

            except Exception as e:
                logger.error(f"Playback error: {e}")
                await search_msg.edit(content="❌ Failed to play audio.")

        except Exception as e:
            logger.error(f"General play command error: {e}")
            await ctx.send("❌ An unexpected error occurred.")

    @commands.command()
    async def stop(self, ctx):
        """หยุดเล่นเพลง"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏹️ Stopped playing.")
        else:
            await ctx.send("Nothing is currently playing.")

    @commands.command()
    async def pause(self, ctx):
        """หยุดเพลงชั่วคราว"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("Nothing is currently playing.")

    @commands.command()
    async def resume(self, ctx):
        """เล่นเพลงต่อ"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("Nothing is currently paused.")

    @commands.command()
    async def volume(self, ctx, volume: int = None):
        """ปรับระดับเสียง (0-100)"""
        if volume is None:
            await ctx.send("Please provide a volume level (0-100).")
            return

        if not 0 <= volume <= 100:
            await ctx.send("Volume must be between 0 and 100.")
            return

        if ctx.voice_client and hasattr(ctx.voice_client.source, 'volume'):
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"🔊 Volume set to {volume}%")
        else:
            await ctx.send("No audio is currently playing or volume control not available.")

    @commands.command()
    async def status(self, ctx):
        """แสดงสถานะปัจจุบันของบอท"""
        if not ctx.voice_client:
            await ctx.send("❌ Not connected to any voice channel.")
            return

        channel = ctx.voice_client.channel
        status = "🔴 Nothing"

        if ctx.voice_client.is_playing():
            status = "🟢 Playing"
        elif ctx.voice_client.is_paused():
            status = "🟡 Paused"

        embed = discord.Embed(
            title="🤖 Bot Status",
            color=0x0099ff
        )
        embed.add_field(name="Voice Channel", value=channel.name, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)

        await ctx.send(embed=embed)

# ฟังก์ชันสำหรับโหลด Cog นี้เข้า bot
async def setup(bot):
    await bot.add_cog(Music(bot))
