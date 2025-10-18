import os
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional
import matplotlib.pyplot as plt
import io
import base64
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['font.family'] = 'DejaVu Sans'

mcp = FastMCP("CHARTS")

CHARTS_DIR = os.path.dirname(os.path.abspath(__file__))

def load_resource_txt(filename: str) -> str:
    resources_dir = os.path.join(CHARTS_DIR, "resources")
    with open(os.path.join(resources_dir, filename), encoding="utf-8") as f:
        return f.read()

def load_prompt_txt(filename: str) -> str:
    prompts_dir = os.path.join(CHARTS_DIR, "prompts")
    with open(os.path.join(prompts_dir, filename), encoding="utf-8") as f:
        return f.read()

# ================================================================================
# CHART GENERATION TOOLS
# ================================================================================

@mcp.tool()
def generate_line_chart(data: List[Dict[str, Any]], x_field: str, y_field: Optional[str] = None, y_fields: Optional[List[str]] = None, title: Optional[str] = None) -> Dict[str, str]:
    """
    Generate a multi-line chart from JSON data using pandas DataFrame. Specify x_field and y_fields for axes.
    Returns a base64-encoded PNG image.
    """
    print(f"[DEBUG] generate_line_chart called with x_field={x_field}, y_field={y_field}, y_fields={y_fields}, title={title}")
    df = pd.DataFrame(data)
    print(f"[DEBUG] DataFrame columns: {df.columns.tolist()}")
    plt.figure(figsize=(8, 6))
    # Use y_fields if provided, else fallback to y_field
    if y_fields is None and y_field is not None:
        y_fields = [y_field]
    if y_fields is None:
        return {"error": "Missing required argument: y_fields or y_field"}
    valid_y_fields = [y for y in y_fields if y in df.columns]
    if not valid_y_fields:
        print(f"[ERROR] None of the y_fields {y_fields} are present in data columns.")
        return {"error": f"None of the y_fields {y_fields} are present in data columns."}
    try:
        print(f"[DEBUG] Plotting lines for y_fields: {valid_y_fields}")
        for y in valid_y_fields:
            print(f"[DEBUG] Plotting y_field: {y}")
            plt.plot(df[x_field], df[y], marker='o', label=y)
        print(f"[DEBUG] Setting xlabel")
        plt.xlabel(x_field)
        print(f"[DEBUG] Setting ylabel")
        plt.ylabel(', '.join(valid_y_fields))
        if title:
            print(f"[DEBUG] Setting title")
            plt.title(title)
        print(f"[DEBUG] Adding legend")
        plt.legend()
        buf = io.BytesIO()
        print(f"[DEBUG] Calling plt.tight_layout()")
        plt.tight_layout()
        print(f"[DEBUG] Calling plt.savefig()")
        plt.savefig(buf, format='png')
        print(f"[DEBUG] Calling plt.close()")
        plt.close()
        print(f"[DEBUG] Seeking buffer to 0")
        buf.seek(0)
        print(f"[DEBUG] Encoding buffer to base64")
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        print(f"[DEBUG] Chart generated and encoded. Returning image_base64.")
        print(f"[DEBUG] Returning: {{'image_base64': <base64 string of length {len(img_b64)}>}}")
        result = {"image_base64": img_b64}
        print(f"[DEBUG] MCP tool response: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] Exception in generate_line_chart: {e}")
        return {"error": f"Exception in generate_line_chart: {e}"}

@mcp.tool()
def generate_bar_chart(data: List[Dict[str, Any]], x_field: str, y_field: Optional[str] = None, y_fields: Optional[List[str]] = None, title: Optional[str] = None) -> Dict[str, str]:
    """
    Generate a multi-bar chart from JSON data using pandas DataFrame. Specify x_field and y_fields for axes.
    Returns a base64-encoded PNG image.
    """
    if not data or not x_field or (y_fields is None and y_field is None):
        return {"error": "Missing required arguments: data, x_field, y_fields or y_field"}
    df = pd.DataFrame(data)
    # Use y_fields if provided, else fallback to y_field
    if y_fields is None and y_field is not None:
        y_fields = [y_field]
    if y_fields is None:
        return {"error": "Missing required argument: y_fields or y_field"}
    if x_field not in df.columns or any(y not in df.columns for y in y_fields):
        return {"error": f"Fields {x_field} or {y_fields} not found in data."}
    plt.figure(figsize=(8, 6))
    bar_width = 0.8 / len(y_fields)
    x = range(len(df[x_field]))
    for idx, y in enumerate(y_fields):
        plt.bar([i + idx * bar_width for i in x], df[y], width=bar_width, label=y)
    plt.xlabel(x_field)
    plt.ylabel(', '.join(y_fields))
    plt.xticks([i + bar_width * (len(y_fields)-1)/2 for i in x], df[x_field])
    if title:
        plt.title(title)
    plt.legend()
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    return {"image_base64": img_b64}

@mcp.tool()
def generate_pie_chart(data: List[Dict[str, Any]], label_field: str, value_field: str, title: Optional[str] = None) -> Dict[str, str]:
    """
    Generate a pie chart from JSON data. Specify label_field for slices and value_field for values.
    Returns a base64-encoded PNG image.
    """
    labels = [item[label_field] for item in data]
    values = [item[value_field] for item in data]
    plt.figure()
    plt.pie(values, labels=labels, autopct='%1.1f%%')
    if title:
        plt.title(title)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    return {"image_base64": img_b64}

def generate_chart(chart_type, data, x_field, y_field, title=None):
    # Convert data to pandas DataFrame
    df = pd.DataFrame(data)
    plt.figure(figsize=(8, 6))
    if chart_type == "bar":
        plt.bar(df[x_field], df[y_field])
    elif chart_type == "line":
        plt.plot(df[x_field], df[y_field], marker='o')
    elif chart_type == "pie":
        plt.pie(df[y_field], labels=df[x_field], autopct='%1.1f%%')
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    plt.xlabel(x_field)
    plt.ylabel(y_field)
    if title:
        plt.title(title)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return image_base64

# ================================================================================
# RESOURCES
# ================================================================================
@mcp.resource("charts://docs/chart_smart_decision")
def chart_smart_decision_doc() -> str:
    return load_resource_txt("docs_chart_smart_decision.txt")

# Add more resources as needed, e.g.:
# @mcp.resource("charts://docs/chart_examples")
# def chart_examples_doc() -> str:
#     return load_resource_txt("docs_chart_examples.txt")

# ================================================================================
# PROMPTS
# ================================================================================
@mcp.prompt("chart_smart_decision")
def chart_smart_decision_prompt() -> str:
    return load_prompt_txt("chart_smart_decision.txt")

# Add more prompts as needed, e.g.:
# @mcp.prompt("chart_examples")
# def chart_examples_prompt() -> str:
#     return load_prompt_txt("chart_examples.txt")

if __name__ == "__main__":
    mcp.run()
