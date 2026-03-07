"""
NightGuard V2 — Discord Bot
"""
import os, sys, time, asyncio, tempfile, traceback, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from cli import obfuscate

TOKEN   = os.environ.get("DISCORD_TOKEN", "")
MAX_SRC = 500_000

# ── Keepalive HTTP server (giữ Render không spin down) ────────────────
class _KA(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *a): pass

def _start_keepalive():
    port = int(os.environ.get("PORT", 8080))
    srv  = HTTPServer(("0.0.0.0", port), _KA)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    print(f"[NightGuard] Keepalive HTTP on port {port}")

# ── Bot setup ─────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ── Helper ────────────────────────────────────────────────────────────
async def send_result(interaction, result, elapsed, in_bytes):
    out_bytes = len(result.encode())
    ratio = out_bytes / max(in_bytes, 1)
    footer = f"⏱ `{elapsed:.2f}s`  📥 `{in_bytes/1024:.1f} KB`  📤 `{out_bytes/1024:.1f} KB`  📈 `{ratio:.1f}x`"
    if out_bytes < 1_900:
        await interaction.followup.send(f"✅ **Obfuscated** — {footer}\n```lua\n{result}\n```")
        return
    with tempfile.NamedTemporaryFile(suffix=".lua", delete=False, mode="w", encoding="utf-8") as f:
        f.write(result)
        tmp = f.name
    try:
        await interaction.followup.send(f"✅ **Obfuscated** — {footer}", file=discord.File(tmp, filename="protected.lua"))
    finally:
        os.unlink(tmp)

# ── /obfuscate ────────────────────────────────────────────────────────
@tree.command(name="obfuscate", description="Obfuscate a Lua script with NightGuard V2 VM")
@app_commands.describe(
    file="Upload a .lua file",
    code="Or paste Lua code directly",
    seed="Optional seed for reproducible output",
)
async def cmd_obfuscate(
    interaction: discord.Interaction,
    file: discord.Attachment | None = None,
    code: str | None = None,
    seed: int | None = None,
):
    # defer NGAY LẬP TỨC - phải xong trước 3 giây
    await interaction.response.defer(thinking=True)

    source = None
    if file is not None:
        if not file.filename.endswith(".lua"):
            await interaction.followup.send("❌ Only `.lua` files are supported.")
            return
        if file.size > MAX_SRC:
            await interaction.followup.send(f"❌ File too large (max {MAX_SRC//1024} KB).")
            return
        source = (await file.read()).decode("utf-8", errors="replace")
    elif code is not None:
        source = code.strip()
        if source.startswith("```"):
            lines = source.split("\n")
            source = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    else:
        await interaction.followup.send("❌ Provide a `.lua` file or `code:`.")
        return

    if not source:
        await interaction.followup.send("❌ Source is empty.")
        return

    loop = asyncio.get_event_loop()
    t0 = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, obfuscate, source, seed),
            timeout=55,
        )
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ Timed out (>55s). Try a smaller script.")
        return
    except SyntaxError as e:
        await interaction.followup.send(f"❌ **Lua parse error:**\n```\n{e}\n```")
        return
    except Exception as e:
        tb = traceback.format_exc()
        await interaction.followup.send(f"❌ **Error:** `{e}`\n```\n{tb[-1500:]}\n```")
        return

    await send_result(interaction, result, time.perf_counter() - t0, len(source.encode()))

# ── /ping ─────────────────────────────────────────────────────────────
@tree.command(name="ping", description="Check bot status")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🟢 NightGuard V2 — `{round(bot.latency*1000)}ms`")

# ── /help ─────────────────────────────────────────────────────────────
@tree.command(name="help", description="How to use NightGuard bot")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(title="NightGuard V2 — Lua Obfuscator", color=0x7c6ff7,
        description="VM-based Lua obfuscator. Compiles to custom bytecode.")
    embed.add_field(name="/obfuscate file:<file.lua>", value="Upload a `.lua` file.", inline=False)
    embed.add_field(name="/obfuscate code:<lua>", value="Paste short Lua code.", inline=False)
    embed.add_field(name="/obfuscate ... seed:<n>", value="Fixed seed for reproducible output.", inline=False)
    embed.set_footer(text="NightGuard V2 • Lua 5.1 / Roblox Luau")
    await interaction.response.send_message(embed=embed)

# ── Ready ─────────────────────────────────────────────────────────────
async def _self_ping():
    """Ping own HTTP endpoint mỗi 10 phút để Render không spin down."""
    await bot.wait_until_ready()
    import aiohttp
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://nightguard-bot.onrender.com")
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    pass
        except Exception:
            pass
        await asyncio.sleep(600)  # 10 phút

@bot.event
async def on_ready():
    await tree.sync()
    print(f"[NightGuard] Logged in as {bot.user} ({bot.user.id})")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="your Lua scripts 🔒"))
    bot.loop.create_task(_self_ping())

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Set DISCORD_TOKEN")
        sys.exit(1)
    _start_keepalive()
    bot.run(TOKEN)
