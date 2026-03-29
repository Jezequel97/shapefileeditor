import math
import os
import tempfile
import zipfile

import geopandas as gpd


def clean_nan(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def load_shapefile_from_upload(upload_file):
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, upload_file.filename)

    with open(zip_path, "wb") as f:
        f.write(upload_file.file.read())

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    shp_file = None
    for filename in os.listdir(temp_dir):
        if filename.endswith(".shp"):
            shp_file = os.path.join(temp_dir, filename)
            break

    if not shp_file:
        raise ValueError("No .shp file found in zip")

    gdf = gpd.read_file(shp_file)
    base_filename = os.path.splitext(os.path.basename(shp_file))[0]

    return gdf, base_filename

def get_columns_types_preview(gdf):
    geometry_col = gdf.geometry.name
    columns = [col for col in gdf.columns if col != geometry_col]

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

    preview = []
    for _, row in gdf.head(5).iterrows():
        preview.append({
            col: clean_nan(row[col])
            for col in columns
        })

    return {
        "columns": columns,
        "types": types,
        "preview": preview
    }

def get_table_data(gdf):
    geometry_col = gdf.geometry.name

    columns = [
        {
            "title": col,
            "field": col
        }
        for col in gdf.columns
        if col != geometry_col
    ]

    rows = []
    for _, row in gdf.iterrows():
        rows.append({
            col: clean_nan(row[col])
            for col in gdf.columns
            if col != geometry_col
        })

    return {
        "columns": columns,
        "rows": rows
    }

def export_shapefile_zip(gdf, filename="result"):
    df = gdf.reset_index(drop=True)
    df = gpd.GeoDataFrame(df, geometry=df.geometry.name)

    if not df.geometry.is_valid.all():
        df = df[df.geometry.is_valid]

    temp_dir = tempfile.mkdtemp()
    shp_path = os.path.join(temp_dir, f"{filename}.shp")

    df.to_file(shp_path, driver="ESRI Shapefile")

    zip_path = os.path.join(temp_dir, f"{filename}.zip")

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in os.listdir(temp_dir):
            if file.endswith((".shp", ".dbf", ".shx", ".prj", ".cpg")):
                zipf.write(
                    os.path.join(temp_dir, file),
                    arcname=file
                )

    return zip_path