import sys
import os

sys.path.append(os.path.dirname(__file__))

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from cli import obfuscate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class Script(BaseModel):
    code:str
    options:dict=None


@app.post("/obfuscate")
def obfuscate_api(script:Script):

    result = obfuscate(script.code, options=script.options)

    return {"result":result}
