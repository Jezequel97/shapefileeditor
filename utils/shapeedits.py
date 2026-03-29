import uuid

def apply_edits(df, data):
    rename = data.get("rename", {})
    delete = data.get("delete", [])
    order = data.get("order", [])
    add = data.get("add", {})

    geometry_col = df.geometry.name

    # rename
    if rename:
        temp_map = {}
        final_map = {}

        for old, new in rename.items():
            temp_name = f"tmp_{uuid.uuid4().hex[:8]}"
            temp_map[old] = temp_name
            final_map[temp_name] = new

        df = df.rename(columns=temp_map)
        df = df.rename(columns=final_map)

    # delete
    for col in delete:
        if col in df.columns and col != geometry_col:
            df = df.drop(columns=[col])

    # add
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

    # reorder
    if order:
        existing_cols = [
            col for col in order
            if col in df.columns and col != geometry_col
        ]
        df = df[existing_cols + [geometry_col]]

    return df

def get_columns_types_preview(df, clean_nan):
    geometry_col = df.geometry.name
    columns = [col for col in df.columns if col != geometry_col]

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

    preview = []
    for _, row in df.head(5).iterrows():
        preview.append({
            col: clean_nan(row[col])
            for col in columns
        })

    return columns, types, preview