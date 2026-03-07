"""
NightGuard V2 — Discord Bot
Commands:
  /obfuscate  — obfuscate a .lua file attachment
  /obfuscate code:<inline code>  — obfuscate inline code
"""
import os, sys, time, asyncio, tempfile, traceback
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from cli import obfuscate

# ── Config ────────────────────────────────────────────────────────────
TOKEN   = os.environ.get("DISCORD_TOKEN", "")
MAX_SRC = 500_000   # 500 KB max source

# ── Bot setup ─────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ── Helper: send long text as file if too big ─────────────────────────
async def send_result(interaction: discord.Interaction, result: str, elapsed: float, in_bytes: int):
    out_bytes = len(result.encode())
    ratio     = out_bytes / max(in_bytes, 1)
    footer    = (
        f"⏱ `{elapsed:.2f}s`  "
        f"📥 `{in_bytes/1024:.1f} KB`  "
        f"📤 `{out_bytes/1024:.1f} KB`  "
        f"📈 `{ratio:.1f}x`"
    )

    # Nếu output ngắn đủ gửi code block
    if out_bytes < 1_900:
        await interaction.followup.send(
            f"✅ **Obfuscated** — {footer}\n```lua\n{result}\n```"
        )
        return

    # Gửi dưới dạng file .lua
    with tempfile.NamedTemporaryFile(suffix=".lua", delete=False, mode="w", encoding="utf-8") as f:
        f.write(result)
        tmp_path = f.name

    try:
        await interaction.followup.send(
            f"✅ **Obfuscated** — {footer}",
            file=discord.File(tmp_path, filename="protected.lua"),
        )
    finally:
        os.unlink(tmp_path)


# ── /obfuscate ────────────────────────────────────────────────────────
@tree.command(name="obfuscate", description="Obfuscate a Lua script with NightGuard V2 VM")
@app_commands.describe(
    file="Upload a .lua file to obfuscate",
    code="Or paste short Lua code directly",
    seed="Optional seed (integer) for reproducible output",
)
async def cmd_obfuscate(
    interaction: discord.Interaction,
    file: discord.Attachment | None = None,
    code: str | None = None,
    seed: int | None = None,
):
    await interaction.response.defer(thinking=True)

    # ── Get source ──
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
        # strip ```lua ... ``` if user wrapped it
        if source.startswith("```"):
            lines = source.split("\n")
            source = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    else:
        await interaction.followup.send(
            "❌ Provide either a `.lua` file attachment or inline `code:`."
        )
        return

    if not source:
        await interaction.followup.send("❌ Source is empty.")
        return

    # ── Run obfuscation in thread (non-blocking) ──
    loop = asyncio.get_event_loop()
    t0   = time.perf_counter()

    try:
        result: str = await asyncio.wait_for(
            loop.run_in_executor(None, obfuscate, source, seed),
            timeout=60,
        )
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ Timed out (>60s). Try a smaller script.")
        return
    except SyntaxError as e:
        await interaction.followup.send(f"❌ **Lua parse error:**\n```\n{e}\n```")
        return
    except Exception as e:
        tb = traceback.format_exc()
        await interaction.followup.send(f"❌ **Error:** `{e}`\n```\n{tb[-1500:]}\n```")
        return

    elapsed = time.perf_counter() - t0
    await send_result(interaction, result, elapsed, len(source.encode()))


# ── /ping ─────────────────────────────────────────────────────────────
@tree.command(name="ping", description="Check if NightGuard bot is alive")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🟢 NightGuard V2 online — `{round(bot.latency * 1000)}ms`"
    )


# ── /help ─────────────────────────────────────────────────────────────
@tree.command(name="help", description="How to use NightGuard bot")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="NightGuard V2 — Lua Obfuscator",
        description="VM-based Lua obfuscator. Compiles to custom bytecode — no loadstring, no readable source.",
        color=0x7c6ff7,
    )
    embed.add_field(
        name="/obfuscate file:<file.lua>",
        value="Upload a `.lua` file and get back the protected version.",
        inline=False,
    )
    embed.add_field(
        name="/obfuscate code:<lua code>",
        value="Paste short Lua code directly in the command.",
        inline=False,
    )
    embed.add_field(
        name="/obfuscate ... seed:<number>",
        value="Use a fixed seed for reproducible output.",
        inline=False,
    )
    embed.set_footer(text="NightGuard V2 • Lua 5.1 / Roblox Luau compatible")
    await interaction.response.send_message(embed=embed)


# ── Ready ─────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"[NightGuard] Logged in as {bot.user} ({bot.user.id})")
    print(f"[NightGuard] Slash commands synced")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="your Lua scripts 🔒"
        )
    )


# ── Run ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Set DISCORD_TOKEN environment variable")
        sys.exit(1)
    bot.run(TOKEN)
