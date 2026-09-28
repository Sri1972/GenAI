"""
Generated MCP server for 'auto-forecast-api-mcp' — tools that call an existing
external API at http://127.0.0.1:8400 directly. Read-only (GET) for v1.
"""
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastmcp import FastMCP

load_dotenv()

BASE_URL = os.environ.get("TARGET_API_BASE_URL", "http://127.0.0.1:8400")
AUTH = (
    (os.environ.get("TARGET_API_USERNAME"), os.environ.get("TARGET_API_PASSWORD"))
    if os.environ.get("TARGET_API_USERNAME") else None
)

mcp = FastMCP("auto-forecast-api-mcp")
mcp_app = mcp.http_app()
app = FastAPI(title="auto-forecast-api-mcp", lifespan=mcp_app.lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@mcp.tool()
def list_vehicle_programs(powertrainTypeId: str = None, segment: str = None, page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of vehicle programs, optionally filtered by powertrain type or vehicle segment."""
    url = BASE_URL + f"/api/v1/vehicle-programs"
    params = {k: v for k, v in {"powertrainTypeId": powertrainTypeId, "segment": segment, "page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_sales_forecasts(vehicleProgramId: str = None, regionId: str = None, period: str = None, page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of sales forecast records, optionally filtered by vehicle program, region, or forecast period."""
    url = BASE_URL + f"/api/v1/sales-forecasts"
    params = {k: v for k, v in {"vehicleProgramId": vehicleProgramId, "regionId": regionId, "period": period, "page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_production_forecasts(productionLineId: str = None, period: str = None, page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of production forecast records, optionally filtered by production line or forecast period."""
    url = BASE_URL + f"/api/v1/production-forecasts"
    params = {k: v for k, v in {"productionLineId": productionLineId, "period": period, "page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_plants(regionId: str = None, page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of manufacturing plants, optionally filtered by region."""
    url = BASE_URL + f"/api/v1/plants"
    params = {k: v for k, v in {"regionId": regionId, "page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_components(category: str = None, page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of components, optionally filtered by component category."""
    url = BASE_URL + f"/api/v1/components"
    params = {k: v for k, v in {"category": category, "page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_usage() -> dict:
    """Get usage statistics for this API."""
    url = BASE_URL + f"/usage"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_health() -> dict:
    """Check the health status of the API service."""
    url = BASE_URL + f"/health"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_vehicle_program_by_id(id: str) -> dict:
    """Retrieve the details of a single vehicle program by its ID."""
    url = BASE_URL + f"/api/v1/vehicle-programs/{id}"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_forecast_accuracy(id: str) -> dict:
    """Retrieve the sales forecast accuracy metrics for a single specified vehicle program."""
    url = BASE_URL + f"/api/v1/vehicle-programs/{id}/forecast-accuracy"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_component_risk(id: str) -> dict:
    """Retrieve the component supply risk assessment for a single specified vehicle program."""
    url = BASE_URL + f"/api/v1/vehicle-programs/{id}/component-risk"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_bill_of_materials(id: str) -> dict:
    """Retrieve the bill of materials associated with a single specified vehicle program."""
    url = BASE_URL + f"/api/v1/vehicle-programs/{id}/bill-of-materials"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_suppliers(page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of component suppliers."""
    url = BASE_URL + f"/api/v1/suppliers"
    params = {k: v for k, v in {"page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_regions(page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of sales/production regions."""
    url = BASE_URL + f"/api/v1/regions"
    params = {k: v for k, v in {"page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_powertrain_mix(id: str) -> dict:
    """Retrieve the breakdown of powertrain types sold or produced within a single specified region."""
    url = BASE_URL + f"/api/v1/regions/{id}/powertrain-mix"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_production_lines(plantId: str = None, vehicleProgramId: str = None, page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of production lines, optionally filtered by plant or vehicle program."""
    url = BASE_URL + f"/api/v1/production-lines"
    params = {k: v for k, v in {"plantId": plantId, "vehicleProgramId": vehicleProgramId, "page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_production_line_by_id(id: str) -> dict:
    """Retrieve the details of a single production line by its ID."""
    url = BASE_URL + f"/api/v1/production-lines/{id}"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_powertrain_types(page: int = None, size: int = None) -> dict:
    """Retrieve a paginated list of available powertrain types."""
    url = BASE_URL + f"/api/v1/powertrain-types"
    params = {k: v for k, v in {"page": page, "size": size}.items() if v is not None}
    resp = httpx.get(url, params=params, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_capacity_utilization(id: str) -> dict:
    """Retrieve the production capacity utilization metrics for a single specified plant."""
    url = BASE_URL + f"/api/v1/plants/{id}/capacity-utilization"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_suppliers(id: str) -> dict:
    """Retrieve the list of suppliers that provide a single specified component."""
    url = BASE_URL + f"/api/v1/components/{id}/suppliers"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_bill_of_material_by_id(id: str) -> dict:
    """Retrieve the details of a single bill-of-materials record by its ID."""
    url = BASE_URL + f"/api/v1/bill-of-materials/{id}"
    resp = httpx.get(url, auth=AUTH, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


app.mount("/", mcp_app)
