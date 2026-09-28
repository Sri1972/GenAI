# auto-forecast-api-mcp

Generated MCP server (api source), served over Streamable HTTP at `/mcp` (also see plain REST routes under `/api/*` if this is a datastore-backed server, and interactive docs at `/docs`).

## Tools

- `list_vehicle_programs` — Retrieve a paginated list of vehicle programs, optionally filtered by powertrain type or vehicle segment.
- `list_sales_forecasts` — Retrieve a paginated list of sales forecast records, optionally filtered by vehicle program, region, or forecast period.
- `list_production_forecasts` — Retrieve a paginated list of production forecast records, optionally filtered by production line or forecast period.
- `list_plants` — Retrieve a paginated list of manufacturing plants, optionally filtered by region.
- `list_components` — Retrieve a paginated list of components, optionally filtered by component category.
- `list_usage` — Get usage statistics for this API.
- `list_health` — Check the health status of the API service.
- `get_vehicle_program_by_id` — Retrieve the details of a single vehicle program by its ID.
- `list_forecast_accuracy` — Retrieve the sales forecast accuracy metrics for a single specified vehicle program.
- `list_component_risk` — Retrieve the component supply risk assessment for a single specified vehicle program.
- `list_bill_of_materials` — Retrieve the bill of materials associated with a single specified vehicle program.
- `list_suppliers` — Retrieve a paginated list of component suppliers.
- `list_regions` — Retrieve a paginated list of sales/production regions.
- `list_powertrain_mix` — Retrieve the breakdown of powertrain types sold or produced within a single specified region.
- `list_production_lines` — Retrieve a paginated list of production lines, optionally filtered by plant or vehicle program.
- `get_production_line_by_id` — Retrieve the details of a single production line by its ID.
- `list_powertrain_types` — Retrieve a paginated list of available powertrain types.
- `list_capacity_utilization` — Retrieve the production capacity utilization metrics for a single specified plant.
- `list_suppliers` — Retrieve the list of suppliers that provide a single specified component.
- `get_bill_of_material_by_id` — Retrieve the details of a single bill-of-materials record by its ID.
