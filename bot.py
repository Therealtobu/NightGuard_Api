"""
NightGuard V3/V4 — Discord Bot
"""
import os, sys, time, asyncio, tempfile, traceback, threading, queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from cli    import obfuscate
from stages import V3_STAGES, V4_STAGES, stage_order, stage_map

TOKEN   = os.environ.get("DISCORD_TOKEN", "")
MAX_SRC = 500_000

# ── Keepalive ─────────────────────────────────────────────────────────────────
class _KA(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *a): pass

def _start_keepalive():
    port = int(os.environ.get("PORT", 8080))
    srv  = HTTPServer(("0.0.0.0", port), _KA)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[NightGuard] Keepalive HTTP on port {port}")

# ── Bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ── Progress embed builder ────────────────────────────────────────────────────
BAR_FILL  = "█"
BAR_EMPTY = "░"
BAR_LEN   = 12

def _bar(pct: float) -> str:
    filled = round(BAR_LEN * pct / 100)
    return BAR_FILL * filled + BAR_EMPTY * (BAR_LEN - filled)

def _stage_line(label: str, state: str) -> str:
    icon = {"done":"🟢","active":"⚙️","error":"🔴"}.get(state, "⚪")
    return f"{icon} {label}"

def build_progress_embed(
    version: int,
    current_stage: str,
    detail: str,
    done_stages: list,
    error_stage: str | None = None,
    elapsed: float = 0.0,
) -> discord.Embed:
    smap   = stage_map(version)
    sorder = stage_order(version)

    # Progress %
    if error_stage and error_stage in sorder:
        idx = sorder.index(error_stage)
    elif current_stage in sorder:
        idx = sorder.index(current_stage)
    else:
        idx = len(sorder)

    pct = round(idx / len(sorder) * 100)

    if error_stage:
        color, title = 0xE74C3C, "❌  Obfuscation Failed"
    elif idx >= len(sorder):
        color, title, pct = 0x2ECC71, "✅  Obfuscation Complete", 100
    else:
        ver_label = f"V{version}"
        color, title = 0x5865F2, f"NightGuard {ver_label} processing 🌌"

    embed = discord.Embed(title=title, color=color)

    # Progress bar
    embed.add_field(
        name  = "Progress",
        value = f"`{_bar(pct)}` **{pct}%**",
        inline= False,
    )

    # Stage list
    lines = []
    for sid in sorder:
        label = smap.get(sid, sid)
        if sid in done_stages:
            lines.append(_stage_line(label, "done"))
        elif sid == error_stage:
            lines.append(_stage_line(label, "error"))
        elif sid == current_stage and not error_stage:
            lines.append(_stage_line(label, "active"))
        else:
            lines.append(_stage_line(label, "pending"))

    embed.add_field(name="Stages", value="\n".join(lines), inline=False)

    # Status box
    active_label = smap.get(current_stage, current_stage)
    if error_stage:
        status = f"Error in {smap.get(error_stage, error_stage)}\n> {detail}"
    elif idx >= len(sorder):
        status = f"All stages complete\n> {elapsed:.2f}s"
    else:
        status = f"{active_label}\n> {detail or 'running...'}"

    embed.add_field(
        name  = "Status",
        value = f"```\n{status[:200]}\n```",
        inline= False,
    )

    embed.set_footer(text=f"NightGuard V{version}  •  ⏱ {elapsed:.2f}s")
    return embed


# ── /obfuscate ────────────────────────────────────────────────────────────────
@tree.command(name="obfuscate",
              description="Obfuscate a Lua script with NightGuard")
@app_commands.describe(
    file    = "Upload a .lua file",
    code    = "Or paste Lua code directly",
    seed    = "Optional seed for reproducible output",
    version = "Obfuscator version: 3 (default) or 4 (stronger)",
    passes  = "V4 only: obfuscation passes 1–3 (default: 2)",
)
async def cmd_obfuscate(
    interaction: discord.Interaction,
    file:    discord.Attachment | None = None,
    code:    str | None  = None,
    seed:    int | None  = None,
    version: str         = "3",
    passes:  int         = 2,
):
    await interaction.response.defer(thinking=True)

    ver = int(version) if version in ("3","4") else 3

    # ── Read source ───────────────────────────────────────────────────────────
    source = None
    if file is not None:
        if not file.filename.endswith(".lua"):
            await interaction.followup.send(embed=discord.Embed(
                title="❌ Invalid file",
                description="Only `.lua` files are supported.",
                color=0xE74C3C))
            return
        if file.size > MAX_SRC:
            await interaction.followup.send(embed=discord.Embed(
                title="❌ File too large",
                description=f"Max size is `{MAX_SRC//1024} KB`.",
                color=0xE74C3C))
            return
        source = (await file.read()).decode("utf-8", errors="replace")
    elif code is not None:
        source = code.strip()
        if source.startswith("```"):
            lines  = source.split("\n")
            source = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )
    else:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ No input",
            description="Provide a `.lua` file or `code:`.",
            color=0xE74C3C))
        return

    if not source:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ Empty source", color=0xE74C3C))
        return

    # ── Live progress ─────────────────────────────────────────────────────────
    prog_q       : queue.Queue = queue.Queue()
    done_stages  : list        = []
    sorder                     = stage_order(ver)
    current_stage              = sorder[0]
    last_detail                = ""
    error_stage                = None
    t0                         = time.perf_counter()

    init_embed = build_progress_embed(ver, current_stage, "Starting…",
                                      done_stages, elapsed=0.0)
    msg = await interaction.followup.send(embed=init_embed)

    # ── Worker thread ─────────────────────────────────────────────────────────
    result_holder: list = [None]
    error_holder:  list = [None]

    def _worker():
        def _cb(stage, detail=""):
            prog_q.put(("stage", stage, detail))
        try:
            result_holder[0] = obfuscate(
                source,
                seed        = seed,
                progress_cb = _cb,
                version     = ver,
                obf_passes  = max(1, min(3, passes)),
            )
            prog_q.put(("done",))
        except Exception as e:
            error_holder[0] = e
            prog_q.put(("error", e))

    loop        = asyncio.get_event_loop()
    worker_task = loop.run_in_executor(None, _worker)

    # ── Poll + edit embed ─────────────────────────────────────────────────────
    EDIT_INTERVAL = 0.8
    last_edit     = time.perf_counter()
    finished      = False

    async def _flush(force=False):
        nonlocal current_stage, last_detail, done_stages, error_stage, last_edit
        changed = False
        while True:
            try:
                item = prog_q.get_nowait()
            except queue.Empty:
                break
            if item[0] == "stage":
                _, stage, detail = item
                if current_stage and current_stage != stage \
                        and current_stage not in done_stages:
                    done_stages.append(current_stage)
                current_stage = stage
                last_detail   = detail
                changed       = True
            elif item[0] in ("done", "error"):
                changed = True
                break

        now = time.perf_counter()
        if (changed or force) and (now - last_edit >= EDIT_INTERVAL or force):
            embed = build_progress_embed(
                ver, current_stage, last_detail,
                done_stages, error_stage=error_stage,
                elapsed=now - t0,
            )
            try:
                await msg.edit(embed=embed)
            except Exception:
                pass
            last_edit = now

    try:
        while not finished:
            await asyncio.sleep(0.3)
            if worker_task.done():
                finished = True
            await _flush(force=finished)
    except asyncio.CancelledError:
        pass

    elapsed = time.perf_counter() - t0

    # ── Error ─────────────────────────────────────────────────────────────────
    if error_holder[0] is not None:
        e          = error_holder[0]
        tb         = traceback.format_exc()
        error_stage = current_stage
        await msg.edit(embed=build_progress_embed(
            ver, current_stage, str(e)[:300],
            done_stages, error_stage=error_stage, elapsed=elapsed,
        ))
        await interaction.followup.send(embed=discord.Embed(
            title="🔴 Error Details",
            description=f"```\n{tb[-1500:]}\n```",
            color=0xE74C3C,
        ))
        return

    # ── Done ──────────────────────────────────────────────────────────────────
    done_stages = list(sorder)
    await msg.edit(embed=build_progress_embed(
        ver, "", "", done_stages, elapsed=elapsed,
    ))

    # ── Result ────────────────────────────────────────────────────────────────
    result    = result_holder[0]
    in_bytes  = len(source.encode())
    out_bytes = len(result.encode())
    ratio     = out_bytes / max(in_bytes, 1)

    result_embed = discord.Embed(
        title       = "🔒 Protected Script",
        description = (
            f"📥 Input   `{in_bytes/1024:.1f} KB`\n"
            f"📤 Output  `{out_bytes/1024:.1f} KB`\n"
            f"📈 Ratio   `{ratio:.1f}x`\n"
            f"⏱ Time    `{elapsed:.2f}s`"
        ),
        color = 0x2ECC71,
    )
    result_embed.set_footer(
        text=f"NightGuard V{ver}  •  Lua 5.1 / Roblox Luau"
    )

    if out_bytes < 1_900:
        result_embed.add_field(
            name="Output",
            value=f"```lua\n{result}\n```",
            inline=False,
        )
        await interaction.followup.send(embed=result_embed)
    else:
        with tempfile.NamedTemporaryFile(
            suffix=".lua", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(result)
            tmp = f.name
        try:
            await interaction.followup.send(
                embed=result_embed,
                file=discord.File(tmp, filename="protected.lua"),
            )
        finally:
            os.unlink(tmp)


# ── /ping ─────────────────────────────────────────────────────────────────────
@tree.command(name="ping", description="Check bot status")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(
        title       = "🟢 NightGuard Online",
        description = f"Latency: `{round(bot.latency*1000)}ms`",
        color       = 0x2ECC71,
    ))


# ── /help ─────────────────────────────────────────────────────────────────────
@tree.command(name="help", description="How to use NightGuard")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title       = "NightGuard — Lua Obfuscator",
        description = (
            "VM-based Lua/Luau obfuscator.\n"
            "**V3** — IronBrew2 tier, fast.\n"
            "**V4** — MoonSec→Luraph tier, double VM + per-script unique keys."
        ),
        color = 0x7C6FF7,
    )
    embed.add_field(
        name   = "/obfuscate file:<file.lua>",
        value  = "Upload a `.lua` file to obfuscate.",
        inline = False,
    )
    embed.add_field(
        name   = "/obfuscate code:<lua>",
        value  = "Paste short Lua code directly.",
        inline = False,
    )
    embed.add_field(
        name   = "/obfuscate ... version:4",
        value  = "Use V4 (stronger, slower). Default: V3.",
        inline = False,
    )
    embed.add_field(
        name   = "/obfuscate ... passes:3",
        value  = "V4 only: more obfuscation passes (1–3). Default: 2.",
        inline = False,
    )
    embed.add_field(
        name   = "/obfuscate ... seed:<n>",
        value  = "Fixed seed for reproducible output.",
        inline = False,
    )
    embed.set_footer(text="NightGuard  •  Lua 5.1 / Roblox Luau")
    await interaction.response.send_message(embed=embed)


# ── Self-ping keepalive ───────────────────────────────────────────────────────
async def _self_ping():
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
        await asyncio.sleep(600)


@bot.event
async def on_ready():
    await tree.sync()
    print(f"[NightGuard] Logged in as {bot.user} ({bot.user.id})")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="your Lua scripts 🔒"))
    bot.loop.create_task(_self_ping())


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Set DISCORD_TOKEN"); sys.exit(1)
    _start_keepalive()
    bot.run(TOKEN)
