"""
NightGuard V2 — Web API
uvicorn main:app --host 0.0.0.0 --port 10000
"""
import os, sys, asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# flat import — tất cả file nằm cùng thư mục
sys.path.insert(0, os.path.dirname(__file__))
from cli import obfuscate

# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(title="NightGuard V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────
class ObfReq(BaseModel):
    code: str = Field(..., max_length=512_000)   # 512 KB limit
    seed: int | None = None

class ObfRes(BaseModel):
    result:       str
    input_bytes:  int
    output_bytes: int

# ── Endpoint ──────────────────────────────────────────────────────────
@app.post("/obfuscate", response_model=ObfRes)
async def api_obfuscate(req: ObfReq):
    src = req.code.strip()
    if not src:
        raise HTTPException(400, "code is empty")

    loop = asyncio.get_event_loop()
    try:
        result: str = await asyncio.wait_for(
            loop.run_in_executor(None, obfuscate, src, req.seed),
            timeout=60,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Timed out — try a smaller script")
    except SyntaxError as e:
        raise HTTPException(400, f"Lua parse error: {e}")
    except Exception as e:
        raise HTTPException(500, f"Obfuscation failed: {e}")

    return ObfRes(
        result=result,
        input_bytes=len(src.encode()),
        output_bytes=len(result.encode()),
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

# ── Static + index ────────────────────────────────────────────────────
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse((STATIC / "index.html").read_text("utf-8"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000, reload=False)
