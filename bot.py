import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

TOKEN = "TOKEN"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# YoutubeDL options
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "downloads/%(title)s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
}

ffmpeg_options = {
    "options": "-vn"
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

if not os.path.exists("downloads"):
    os.makedirs("downloads")


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data=None, filename=None, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.filename = filename
        self.title = data.get("title") if data else os.path.basename(filename)

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        # Check if URL is a local file path
        if os.path.isfile(url):
            return cls(discord.FFmpegPCMAudio(url, **ffmpeg_options), filename=url)

        # Otherwise treat as YouTube URL
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=True)
        )
        if "entries" in data:
            data = data["entries"][0]
        filename = ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, filename=filename)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


que = []

@bot.command()
async def play(ctx, source: str):
    if ctx.author.voice is None:
        await ctx.send("Et ole voice channelillä.")
        return

    que.append({
        "ctx": ctx,
        "source": source
    })

    vc = ctx.voice_client
    if not vc or not vc.is_playing():
        await execute_play()
    else:
        player = await YTDLSource.from_url(source, loop=bot.loop)
        msg = "**Lisätty jonoon sijalle " + str((len(que) + 1)) + ":** " + player.title
        await ctx.send(msg)


def cleanup_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except PermissionError:
                # File is still in use — ignore
                pass
            except Exception as e:
                print(f"Unexpected error deleting {file_path}: {e}")

async def execute_play():
    if(len(que) == 0):
        return

    data = que.pop(0)

    ctx = data["ctx"]
    source = data["source"]

    voice_channel = ctx.author.voice.channel
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if vc is None:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await vc.move_to(voice_channel)

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(source, loop=bot.loop)
        except Exception as e:
            await ctx.send("Virhe.")
            print(e)
            return

        vc.stop()

        def after_playing(error):
            if error:
                print(error)
            cleanup_folder("downloads")
            asyncio.run_coroutine_threadsafe(execute_play(), bot.loop)

        vc.play(player, after=after_playing)

    await ctx.send(f"Soitetaan: **{player.title}**")


@bot.command()
async def stop(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("Pysäytetty.")


@bot.command()
async def leave(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc:
        await vc.disconnect()
        await ctx.send("Disconnected.")


@bot.command()
async def skip(ctx):
    vc = ctx.voice_client
    if not vc or not vc.is_playing():
        return

    vc.stop()
    await ctx.send("Skipattiin.")

@bot.command()
async def jono(ctx):
    res = ""
    if(len(que) == 0):
        await ctx.send("Jono on tyhjä")
    for a in range(0, len(que)):
        q = que[a]
        player = await YTDLSource.from_url(q["source"], loop=bot.loop)
        res += str(a + 1) + ". " + player.title + "\n"
    await ctx.send(res)

bot.run(TOKEN)
