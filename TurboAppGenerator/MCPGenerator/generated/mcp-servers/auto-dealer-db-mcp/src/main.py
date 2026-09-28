"""
Generated MCP server for 'auto-dealer-db-mcp' — tools that call this project's
own backing API at http://127.0.0.1:8402 (see the Web API tab) for the actual data.
"""
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastmcp import FastMCP

load_dotenv()

BASE_URL = os.environ.get("BACKING_API_BASE_URL", "http://127.0.0.1:8402")

mcp = FastMCP("auto-dealer-db-mcp")
mcp_app = mcp.http_app()
app = FastAPI(title="auto-dealer-db-mcp", lifespan=mcp_app.lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@mcp.tool()
def list_customers(page: int = 0, limit: int = 20) -> dict:
    """List rows from the customers table."""
    resp = httpx.get(BASE_URL + "/api/customers", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_customer(id: str) -> dict:
    """Get a single row from the customers table by its id."""
    url = BASE_URL + f"/api/customers/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_dealerships(page: int = 0, limit: int = 20) -> dict:
    """List rows from the dealerships table."""
    resp = httpx.get(BASE_URL + "/api/dealerships", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_dealership(id: str) -> dict:
    """Get a single row from the dealerships table by its id."""
    url = BASE_URL + f"/api/dealerships/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_manufacturers(page: int = 0, limit: int = 20) -> dict:
    """List rows from the manufacturers table."""
    resp = httpx.get(BASE_URL + "/api/manufacturers", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_manufacturer(id: str) -> dict:
    """Get a single row from the manufacturers table by its id."""
    url = BASE_URL + f"/api/manufacturers/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_parts(page: int = 0, limit: int = 20) -> dict:
    """List rows from the parts table."""
    resp = httpx.get(BASE_URL + "/api/parts", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_part(id: str) -> dict:
    """Get a single row from the parts table by its id."""
    url = BASE_URL + f"/api/parts/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_salespeople(page: int = 0, limit: int = 20) -> dict:
    """List rows from the salespeople table."""
    resp = httpx.get(BASE_URL + "/api/salespeople", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_salespeople(id: str) -> dict:
    """Get a single row from the salespeople table by its id."""
    url = BASE_URL + f"/api/salespeople/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_service_centers(page: int = 0, limit: int = 20) -> dict:
    """List rows from the service_centers table."""
    resp = httpx.get(BASE_URL + "/api/service_centers", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_service_center(id: str) -> dict:
    """Get a single row from the service_centers table by its id."""
    url = BASE_URL + f"/api/service_centers/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_vehicle_models(page: int = 0, limit: int = 20) -> dict:
    """List rows from the vehicle_models table."""
    resp = httpx.get(BASE_URL + "/api/vehicle_models", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_vehicle_model(id: str) -> dict:
    """Get a single row from the vehicle_models table by its id."""
    url = BASE_URL + f"/api/vehicle_models/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_technicians(page: int = 0, limit: int = 20) -> dict:
    """List rows from the technicians table."""
    resp = httpx.get(BASE_URL + "/api/technicians", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_technician(id: str) -> dict:
    """Get a single row from the technicians table by its id."""
    url = BASE_URL + f"/api/technicians/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_vehicles(page: int = 0, limit: int = 20) -> dict:
    """List rows from the vehicles table."""
    resp = httpx.get(BASE_URL + "/api/vehicles", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_vehicle(id: str) -> dict:
    """Get a single row from the vehicles table by its id."""
    url = BASE_URL + f"/api/vehicles/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_sales(page: int = 0, limit: int = 20) -> dict:
    """List rows from the sales table."""
    resp = httpx.get(BASE_URL + "/api/sales", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_sale(id: str) -> dict:
    """Get a single row from the sales table by its id."""
    url = BASE_URL + f"/api/sales/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_service_appointments(page: int = 0, limit: int = 20) -> dict:
    """List rows from the service_appointments table."""
    resp = httpx.get(BASE_URL + "/api/service_appointments", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_service_appointment(id: str) -> dict:
    """Get a single row from the service_appointments table by its id."""
    url = BASE_URL + f"/api/service_appointments/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_service_order_parts(page: int = 0, limit: int = 20) -> dict:
    """List rows from the service_order_parts table."""
    resp = httpx.get(BASE_URL + "/api/service_order_parts", params={"page": page, "limit": limit}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_service_order_part(id: str) -> dict:
    """Get a single row from the service_order_parts table by its id."""
    url = BASE_URL + f"/api/service_order_parts/{id}"
    resp = httpx.get(url, timeout=15.0)
    if resp.status_code == 404:
        return {"error": "Not found"}
    resp.raise_for_status()
    return resp.json()


app.mount("/", mcp_app)
