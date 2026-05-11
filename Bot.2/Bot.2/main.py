import discord
from discord.ext import commands
import yt_dlp
import asyncio
import sqlite3
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.ERROR)
# Carrega o arquivo .env do diretório atual
env_path = os.path.join(os.path.dirname(__file__), '.env')
print(f"Buscando .env em: {env_path}")
print(f"Arquivo existe: {os.path.exists(env_path)}")

# Tenta carregar com load_dotenv
load_dotenv(r"C:\Users\Viii2\Desktop\bot.2\.env")

# Se não encontrar, lê manualmente
token = os.getenv("DISCORD_TOKEN")

if not token and os.path.exists(env_path):
    print("Tentando ler .env manualmente...")
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            print(f"Conteúdo do .env: {content[:50]}...")
            if content.startswith("DISCORD_TOKEN="):
                token = content.replace("DISCORD_TOKEN=", "").strip()
                print(f"Token extraído manualmente: {token[:20]}...")
    except Exception as e:
        print(f"Erro ao ler .env manualmente: {e}")

print(f"TOKEN DEBUG: {token[:20] if token else 'NONE'}...")

if not token:
    print(f"Erro: TOKEN não encontrado em {env_path}")
    print("Variáveis de ambiente disponíveis:")
    for key in os.environ:
        if 'TOKEN' in key.upper() or 'DISCORD' in key.upper():
            print(f"  {key} = {os.environ[key][:20]}...")
    raise SystemExit("TOKEN NÃO CARREGADO")

# ================== DISCORD CONFIG ==================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="j!", intents=intents)

# ================== ESTRUTURAS ==================
queues = {}
user_playlists = {}

# ================== PLAYER ==================
def play_next(ctx):
    queue = queues.get(ctx.guild.id)

    if not queue:
        return

    url = queue.pop(0)
    play_audio(ctx, url, retries=2)


def play_audio(ctx, url, retries=2):
    ydl_opts = {
        'format': 'bestaudio',
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url_audio = info['url']
    except Exception as e:
        print("Erro ao extrair:", e)
        return play_next(ctx)

    source = discord.FFmpegPCMAudio(
        url_audio,
        before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        options='-vn'
    )

    def after(error):
        if error:
            print("Erro no player:", error)

            if retries > 0:
                print("Tentando novamente...")
                return play_audio(ctx, url, retries - 1)

        play_next(ctx)

    ctx.voice_client.play(source, after=after)

# ================== BANCO ==================
def add_music(user_id, url):
    conn = sqlite3.connect('playlists.db')
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO PLAYLISTS (USER_ID, URL) VALUES (?, ?)",
        (user_id, url)
    )

    conn.commit()
    conn.close()


def get_playlists(user_id):
    conn = sqlite3.connect('playlists.db')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT URL FROM PLAYLISTS WHERE USER_ID = ?",
        (user_id,)
    )

    musicas = [row[0] for row in cursor.fetchall()]

    conn.close()
    return musicas


def remove_music(user_id, url):
    conn = sqlite3.connect('playlists.db')
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM PLAYLISTS WHERE USER_ID = ? AND URL = ?",
        (user_id, url)
    )

    conn.commit()
    conn.close()

# ================== COMANDOS ==================
@bot.command()
async def entrar(ctx):
    if not ctx.author.voice:
        await ctx.send("Entre em um canal de voz.")
        return

    channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc and vc.channel != channel:
        await vc.move_to(channel)
    
    else: 
        try:
            await channel.connect(reconnect=True, timeout=30)
        except Exception as e:
            await ctx.send(f"Erro ao conectar: {e}")

       


@bot.command()
async def tocar(ctx, *, url):
    if not ctx.author.voice:
        await ctx.send("Entre em um canal de voz.")
        return

    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []

    queues[ctx.guild.id].append(url)

    vc = ctx.voice_client

    if not vc or not vc.is_connected():
        vc = await ctx.author.voice.channel.connect(
            reconnect=True,
            timeout=30
        )

        await asyncio.sleep(2)

    if not vc.is_playing():
        play_next(ctx)

    await ctx.send("Adicionado à fila!")


# ================== PLAYLIST PERSONALIZADA ==================
@bot.command()
async def addplaylist(ctx, *, url):
    add_music(ctx.author.id, url)
    await ctx.send("Adicionada à sua playlist pessoal!")


@bot.command()
async def minha_playlist(ctx):
    playlist = get_playlists(ctx.author.id)

    if not playlist:
        await ctx.send("Sua playlist está vazia.")
        return

    msg = "\n".join(playlist)
    await ctx.send(f"Sua playlist:\n{msg}")


@bot.command()
async def tocarplaylist(ctx): 
    playlist = get_playlists(ctx.author.id)

    if not playlist:
        await ctx.send("Sua playlist está vazia.")
        return

    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []

    queue = queues[ctx.guild.id]
    queue.extend(playlist)

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    if not ctx.voice_client.is_playing():
        play_next(ctx)

    await ctx.send("Sua playlist foi adicionada na fila!")

# ================== CONTROLES ==================
@bot.command()
async def pausar(ctx):
    if ctx.voice_client:
        ctx.voice_client.pause()


@bot.command()
async def continuar(ctx):
    if ctx.voice_client:
        ctx.voice_client.resume()


@bot.command()
async def lista(ctx):
    queue = queues.get(ctx.guild.id, [])

    if not queue:
        await ctx.send("Fila vazia.")
    else:
        msg = "\n".join(queue)
        await ctx.send(f"Fila:\n{msg}")


@bot.command()
async def pular(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()


@bot.command()
async def sair(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

# ================== CRIAR BANCO ==================
conn = sqlite3.connect('playlists.db')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS PLAYLISTS (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    USER_ID INTEGER,
    URL TEXT
)
""")

conn.commit()
conn.close()

bot.run(token)