"""
NightGuard V2 — Discord Bot
"""
import os, sys, time, asyncio, tempfile, traceback, threading, queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from cli import obfuscate, STAGES

TOKEN   = os.environ.get("DISCORD_TOKEN", "")
MAX_SRC = 500_000

# ── Keepalive ─────────────────────────────────────────────────────────
class _KA(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *a): pass

def _start_keepalive():
    port = int(os.environ.get("PORT", 8080))
    srv  = HTTPServer(("0.0.0.0", port), _KA)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[NightGuard] Keepalive HTTP on port {port}")

# ── Bot ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ── Embed builder ─────────────────────────────────────────────────────
STAGE_NAMES = {k: v for k, v in STAGES}  # id → label
STAGE_ORDER = [k for k, _ in STAGES]     # ordered list of ids

BAR_FILL  = "█"
BAR_EMPTY = "░"
BAR_LEN   = 12

def _bar(pct: float) -> str:
    filled = round(BAR_LEN * pct / 100)
    return BAR_FILL * filled + BAR_EMPTY * (BAR_LEN - filled)

def _stage_line(sid: str, state: str) -> str:
    """state: 'done' | 'active' | 'pending' | 'error'"""
    label = STAGE_NAMES.get(sid, sid)
    if state == "done":
        icon = "🟢"
    elif state == "active":
        icon = "⚙️"
    elif state == "error":
        icon = "🔴"
    else:
        icon = "⚪"
    return f"{icon} {label}"

def build_progress_embed(
    current_stage: str,
    detail: str,
    done_stages: list,
    error_stage: str | None = None,
    elapsed: float = 0.0,
) -> discord.Embed:
    # Figure out progress %
    if error_stage:
        idx = STAGE_ORDER.index(error_stage) if error_stage in STAGE_ORDER else len(STAGE_ORDER)
    elif current_stage in STAGE_ORDER:
        idx = STAGE_ORDER.index(current_stage)
    else:
        idx = len(STAGE_ORDER)

    pct = round(idx / len(STAGE_ORDER) * 100)

    if error_stage:
        color = 0xE74C3C  # red
        title = "❌  Obfuscation Failed"
    elif idx >= len(STAGE_ORDER):
        color = 0x2ECC71  # green
        title = "✅  Obfuscation Complete"
        pct   = 100
    else:
        color = 0x5865F2  # blurple
        title = "NightGuard processing 🌌"

    embed = discord.Embed(title=title, color=color)

    # Progress bar row
    bar = _bar(pct)
    embed.add_field(
        name="Progress",
        value=f"`{bar}` **{pct}%**",
        inline=False,
    )

    # Stages column
    lines = []
    for sid in STAGE_ORDER:
        if sid in done_stages:
            lines.append(_stage_line(sid, "done"))
        elif sid == error_stage:
            lines.append(_stage_line(sid, "error"))
        elif sid == current_stage and not error_stage:
            lines.append(_stage_line(sid, "active"))
        else:
            lines.append(_stage_line(sid, "pending"))

    embed.add_field(name="Stages", value="\n".join(lines), inline=False)

    # Status box — what's happening right now
    if error_stage:
        status_text = f"Error in {STAGE_NAMES.get(error_stage, error_stage)}\n> {detail}"
    elif idx >= len(STAGE_ORDER):
        status_text = f"All stages complete\n> {elapsed:.2f}s"
    else:
        active_label = STAGE_NAMES.get(current_stage, current_stage)
        status_text  = f"{active_label}\n> {detail}" if detail else f"{active_label}\n> running..."

    embed.add_field(
        name="Status",
        value=f"```\n{status_text[:200]}\n```",
        inline=False,
    )

    embed.set_footer(text=f"NightGuard V2  •  ⏱ {elapsed:.2f}s")
    return embed

# ── /obfuscate ────────────────────────────────────────────────────────
@tree.command(name="obfuscate", description="Obfuscate a Lua script with NightGuard V2")
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
    await interaction.response.defer(thinking=True)

    # ── Read source ────────────────────────────────────────────────────
    source = None
    if file is not None:
        if not file.filename.endswith(".lua"):
            await interaction.followup.send(embed=discord.Embed(
                title="❌ Invalid file", description="Only `.lua` files are supported.", color=0xE74C3C))
            return
        if file.size > MAX_SRC:
            await interaction.followup.send(embed=discord.Embed(
                title="❌ File too large",
                description=f"Max size is `{MAX_SRC//1024} KB`.", color=0xE74C3C))
            return
        source = (await file.read()).decode("utf-8", errors="replace")
    elif code is not None:
        source = code.strip()
        if source.startswith("```"):
            lines  = source.split("\n")
            source = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    else:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ No input", description="Provide a `.lua` file or `code:`.", color=0xE74C3C))
        return

    if not source:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ Empty source", color=0xE74C3C))
        return

    # ── Live progress state ────────────────────────────────────────────
    prog_q: queue.Queue = queue.Queue()   # (stage, detail) pushed from worker thread
    done_stages: list   = []
    current_stage       = STAGE_ORDER[0]
    last_detail         = ""
    error_stage         = None
    t0                  = time.perf_counter()

    # Send initial embed
    init_embed = build_progress_embed(current_stage, "Starting…", done_stages, elapsed=0.0)
    msg = await interaction.followup.send(embed=init_embed)

    # ── Run obfuscate in background thread ─────────────────────────────
    result_holder: list = [None]
    error_holder:  list = [None]

    def _worker():
        def _cb(stage, detail=""):
            prog_q.put(("stage", stage, detail))
        try:
            result_holder[0] = obfuscate(source, seed=seed, progress_cb=_cb)
            prog_q.put(("done",))
        except Exception as e:
            error_holder[0] = e
            prog_q.put(("error", e))

    loop = asyncio.get_event_loop()
    worker_task = loop.run_in_executor(None, _worker)

    # ── Poll queue and update embed ────────────────────────────────────
    EDIT_INTERVAL = 0.8   # seconds between Discord edits (rate-limit safe)
    last_edit     = time.perf_counter()
    finished      = False

    async def _flush_and_edit(force=False):
        nonlocal current_stage, last_detail, done_stages, error_stage, last_edit
        changed = False
        while True:
            try:
                item = prog_q.get_nowait()
            except queue.Empty:
                break
            if item[0] == "stage":
                _, stage, detail = item
                if current_stage and current_stage != stage and current_stage not in done_stages:
                    done_stages.append(current_stage)
                current_stage = stage
                last_detail   = detail
                changed       = True
            elif item[0] in ("done", "error"):
                changed = True
                break

        now = time.perf_counter()
        if changed or force:
            if now - last_edit >= EDIT_INTERVAL or force:
                embed = build_progress_embed(
                    current_stage, last_detail, done_stages,
                    error_stage=error_stage,
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
            # Check if worker finished
            if worker_task.done():
                finished = True
            # Drain queue
            await _flush_and_edit(force=finished)
    except asyncio.CancelledError:
        pass

    elapsed = time.perf_counter() - t0

    # ── Handle error ───────────────────────────────────────────────────
    if error_holder[0] is not None:
        e  = error_holder[0]
        tb = traceback.format_exc()
        # Mark current stage red
        error_stage = current_stage
        err_embed   = build_progress_embed(
            current_stage, str(e)[:300],
            done_stages, error_stage=error_stage, elapsed=elapsed,
        )
        await msg.edit(embed=err_embed)

        detail_embed = discord.Embed(
            title       = "🔴 Error Details",
            description = f"```\n{tb[-1500:]}\n```",
            color       = 0xE74C3C,
        )
        await interaction.followup.send(embed=detail_embed)
        return

    # ── Mark all done ──────────────────────────────────────────────────
    done_stages = list(STAGE_ORDER)
    final_embed = build_progress_embed(
        "", "", done_stages, elapsed=elapsed,
    )
    await msg.edit(embed=final_embed)

    # ── Send result ────────────────────────────────────────────────────
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
    result_embed.set_footer(text="NightGuard V2 • Lua 5.1 / Roblox Luau")

    if out_bytes < 1_900:
        result_embed.add_field(name="Output", value=f"```lua\n{result}\n```", inline=False)
        await interaction.followup.send(embed=result_embed)
    else:
        with tempfile.NamedTemporaryFile(suffix=".lua", delete=False, mode="w", encoding="utf-8") as f:
            f.write(result)
            tmp = f.name
        try:
            await interaction.followup.send(
                embed=result_embed,
                file=discord.File(tmp, filename="protected.lua"),
            )
        finally:
            os.unlink(tmp)

# ── /ping ─────────────────────────────────────────────────────────────
@tree.command(name="ping", description="Check bot status")
async def cmd_ping(interaction: discord.Interaction):
    embed = discord.Embed(
        title       = "🟢 NightGuard V2 Online",
        description = f"Latency: `{round(bot.latency*1000)}ms`",
        color       = 0x2ECC71,
    )
    await interaction.response.send_message(embed=embed)

# ── /help ─────────────────────────────────────────────────────────────
@tree.command(name="help", description="How to use NightGuard bot")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title       = "NightGuard V2 — Lua Obfuscator",
        description = "VM-based Lua obfuscator. Compiles to custom bytecode with encrypted dispatch table, polymorphic bytecode, and per-build VM mutation.",
        color       = 0x7C6FF7,
    )
    embed.add_field(name="/obfuscate file:<file.lua>", value="Upload a `.lua` file to obfuscate.", inline=False)
    embed.add_field(name="/obfuscate code:<lua>",      value="Paste short Lua code directly.",       inline=False)
    embed.add_field(name="/obfuscate ... seed:<n>",    value="Fixed seed for reproducible output.",  inline=False)
    embed.set_footer(text="NightGuard V2 • Lua 5.1 / Roblox Luau")
    await interaction.response.send_message(embed=embed)

# ── Self-ping keepalive ───────────────────────────────────────────────
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
