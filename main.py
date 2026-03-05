"""
NightGuard V2 — Web API
No pydantic — dùng dict thuần để tránh mọi vấn đề Python version
Deploy: uvicorn main:app --host 0.0.0.0 --port 10000
"""
import os, sys, asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import obfuscate

app = FastAPI(title="NightGuard V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_BYTES = 512_000  # 512 KB

@app.post("/obfuscate")
async def api_obfuscate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    code = body.get("code", "").strip()
    seed = body.get("seed", None)

    if not code:
        return JSONResponse({"error": "code is empty"}, status_code=400)
    if len(code.encode()) > MAX_BYTES:
        return JSONResponse({"error": "Script too large (max 512 KB)"}, status_code=413)

    loop = asyncio.get_event_loop()
    try:
        result: str = await asyncio.wait_for(
            loop.run_in_executor(None, obfuscate, code, seed),
            timeout=60,
        )
    except asyncio.TimeoutError:
        return JSONResponse({"error": "Timed out — try a smaller script"}, status_code=504)
    except SyntaxError as e:
        return JSONResponse({"error": f"Lua parse error: {e}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Obfuscation failed: {e}"}, status_code=500)

    return JSONResponse({
        "result":       result,
        "input_bytes":  len(code.encode()),
        "output_bytes": len(result.encode()),
    })

@app.get("/health")
async def health():
    return {"status": "ok"}

STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse((STATIC / "index.html").read_text("utf-8"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000, reload=False)
