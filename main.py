from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from utils.shapeedits import apply_edits, get_columns_types_preview
from utils.shapefile import (
    load_shapefile_from_upload,
    get_columns_types_preview,
    export_shapefile_zip,
    get_table_data
)

import geopandas as gpd
import pandas as pd
import zipfile
import os
import tempfile
import shutil
import uuid
import math

app = FastAPI()

# static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 🌐 frontend serveren
@app.get("/")
@app.get("/app")
def serve_frontend(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# 🌐 tweede pagina
@app.get("/editor")
def serve_editor(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={}
    )


# Redirects
@app.middleware("http")
async def redirect_domains(request: Request, call_next):
    host = request.headers.get("host", "").lower()

    print("HOST:", host)  # debug

    if any(domain in host for domain in [
        "shapefileeditor.net",
        "shapefileeditor.io"
    ]):
        return RedirectResponse(
            url=f"https://shapefileeditor.com{request.url.path}",
            status_code=301
        )

    return await call_next(request)

# globals (MVP)
LAST_DF = None
LAST_FILENAME = None

# 📤 Upload kolommen
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global LAST_DF, LAST_FILENAME

    try:
        LAST_DF, LAST_FILENAME = load_shapefile_from_upload(file)
        return get_columns_types_preview(LAST_DF)

    except Exception as e:
        return {"error": str(e)}

# 📤 Upload data
@app.post("/upload-table")
async def upload_table(file: UploadFile = File(...)):
    global LAST_DF, LAST_FILENAME

    try:
        LAST_DF, LAST_FILENAME = load_shapefile_from_upload(file)

        data = get_table_data(LAST_DF)
        print("UPLOAD TABLE OK")
        print("ROWS:", len(data["rows"]))
        print("COLUMNS:", data["columns"])

        return data

    except Exception as e:
        print("UPLOAD TABLE ERROR:", repr(e))
        return {"error": str(e)}

# ✏️ Edit kolommen
@app.post("/edit")
async def edit(data: dict):
    global LAST_DF

    if LAST_DF is None:
        return {"error": "No data loaded"}
    
    print("before:", LAST_DF.columns.tolist())
    LAST_DF = apply_edits(LAST_DF.copy(), data)
    print("after:", LAST_DF.columns.tolist())

    return get_columns_types_preview(LAST_DF)

# ✏️ Edit data
@app.post("/edit-table")
async def edit_table(data: dict):
    global LAST_DF

    if LAST_DF is None:
        return {"error": "No data loaded"}
    
     # eerst kolommen hernoemen indien meegestuurd
    rename = data.get("rename", {})

    if rename:
        LAST_DF = apply_edits(LAST_DF.copy(), {
            "rename": rename
        })
    
    rows = data.get("rows", [])

    geometry_col = LAST_DF.geometry.name

    for i, row in enumerate(rows):
        for col, value in row.items():
            if col != geometry_col and col in LAST_DF.columns:
                LAST_DF.at[i, col] = value

    return {"success": True}

# 📥 Download endpoint

@app.get("/download")
def download():
    global LAST_DF, LAST_FILENAME

    if LAST_DF is None:
        return {"error": "No data available"}

    try:
        zip_path = export_shapefile_zip(
            LAST_DF,
            LAST_FILENAME or "result"
        )

        return FileResponse(
            path=zip_path,
            filename=f"{LAST_FILENAME or 'result'}.zip",
            media_type="application/zip"
        )

    except Exception as e:
        return {"error": str(e)}