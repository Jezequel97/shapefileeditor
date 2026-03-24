from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

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

# globals (MVP)
LAST_DF = None
LAST_FILENAME = None


# 🔧 helper: NaN veilig maken voor JSON
def clean_nan(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# 📤 Upload endpoint
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global LAST_DF, LAST_FILENAME

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)

    # save zip
    with open(zip_path, "wb") as f:
        f.write(await file.read())

    # unzip
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # find shp
    shp_file = None
    for f in os.listdir(temp_dir):
        if f.endswith(".shp"):
            shp_file = os.path.join(temp_dir, f)
            break

    if not shp_file:
        return {"error": "No .shp file found in zip"}

    # read shapefile
    gdf = gpd.read_file(shp_file)

    LAST_DF = gdf
    LAST_FILENAME = os.path.splitext(os.path.basename(shp_file))[0]

    # columns WITHOUT geometry
    geometry_col = gdf.geometry.name
    columns = [col for col in gdf.columns if col != geometry_col]

    # types
    types = {}
    for col in columns:
        dtype = str(gdf[col].dtype)
        if "int" in dtype:
            types[col] = "int"
        elif "float" in dtype:
            types[col] = "float"
        elif "bool" in dtype:
            types[col] = "bool"
        else:
            types[col] = "string"

    # preview (first 5 rows)
    preview = []
    for _, row in gdf.head(5).iterrows():
        clean_row = {}
        for col in columns:
            clean_row[col] = clean_nan(row[col])
        preview.append(clean_row)

    return {
        "columns": columns,
        "types": types,
        "preview": preview
    }


# ✏️ Edit endpoint
@app.post("/edit")
async def edit(data: dict):
    global LAST_DF

    if LAST_DF is None:
        return {"error": "No data loaded"}

    df = LAST_DF.copy()

    rename = data.get("rename", {})
    delete = data.get("delete", [])
    order = data.get("order", [])
    add = data.get("add", {})

    print("ADD RECEIVED:", add)

    geometry_col = df.geometry.name

    # 1. rename

    if rename:
        temp_map = {}
        final_map = {}

        # 🔥 stap 1: alles naar tijdelijke namen
        for old, new in rename.items():
            temp_name = f"tmp_{uuid.uuid4().hex[:8]}"
            temp_map[old] = temp_name
            final_map[temp_name] = new

        # 🔥 eerst naar temp
        df = df.rename(columns=temp_map)

        # 🔥 daarna naar definitief
        df = df.rename(columns=final_map)

    # 2. delete
    for col in delete:
        if col in df.columns and col != geometry_col:
            df = df.drop(columns=[col])

    # 3. add (🔥 vóór reorder)
    for col_name, config in add.items():
        if col_name not in df.columns and col_name != geometry_col:
            dtype = config.get("type", "string")
            default = config.get("default", "")

            if dtype == "int":
                df[col_name] = int(default) if default != "" else 0
            elif dtype == "float":
                df[col_name] = float(default) if default != "" else 0.0
            elif dtype == "bool":
                df[col_name] = bool(default)
            else:
                df[col_name] = str(default)

    # 4. reorder (🔥 geometry behouden!)
    if order:
        existing_cols = [col for col in order if col in df.columns and col != geometry_col]
        df = df[existing_cols + [geometry_col]]

    # 🔁 opslaan
    LAST_DF = df

    # return columns (zonder geometry)
    columns = [col for col in df.columns if col != geometry_col]

    # types opnieuw bepalen
    types = {}
    for col in columns:
        dtype = str(df[col].dtype)
        if "int" in dtype:
            types[col] = "int"
        elif "float" in dtype:
            types[col] = "float"
        elif "bool" in dtype:
            types[col] = "bool"
        else:
            types[col] = "string"

    return {
        "columns": columns,
        "types": types
    }


# 📥 Download endpoint

@app.get("/download")
def download():
    global LAST_DF, LAST_FILENAME

    if LAST_DF is None:
        return {"error": "No data available"}

    print("STEP 1: start download")

    try:
        # 🔹 reset index (voorkomt export issues)
        df = LAST_DF.reset_index(drop=True)

        # 🔹 force GeoDataFrame
        df = gpd.GeoDataFrame(df, geometry=df.geometry.name)

        # 🔹 check geometry validity
        if not df.geometry.is_valid.all():
            print("⚠️ Invalid geometries found → filtering")
            df = df[df.geometry.is_valid]

        print("STEP 2: geometry OK")

        # 🔹 unieke tijdelijke map (voorkomt file lock issues)
        folder = tempfile.mkdtemp()

        filename = LAST_FILENAME or "result"
        shp_path = os.path.join(folder, f"{filename}.shp")

        print("STEP 3: writing shapefile")

        # 🔹 schrijf shapefile
        df.to_file(shp_path, driver="ESRI Shapefile")

        print("STEP 4: shapefile written")

        # 🔹 zip alles (shapefile bestaat uit meerdere files)

        zip_path = os.path.join(folder, f"{filename}.zip")

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in os.listdir(folder):
                if file.endswith((".shp", ".dbf", ".shx", ".prj", ".cpg")):
                    zipf.write(
                        os.path.join(folder, file),
                        arcname=file
                    )

        print("STEP 5: zip created")
        print("DOWNLOAD CALLED")
        print("FILENAME:", LAST_FILENAME)
        print("DF EMPTY:", LAST_DF is None)
        print("FILES IN FOLDER:", os.listdir(folder))
        print("ZIP PATH:", zip_path)
        print("EXISTS:", os.path.exists(zip_path))

        return FileResponse(
            path=zip_path,
            filename=f"{filename}.zip",
            media_type="application/zip"
        )

    except Exception as e:
        print("❌ DOWNLOAD ERROR:", e)
        return {"error": str(e)}


# 🌐 frontend serveren
@app.get("/app", response_class=HTMLResponse)
def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()