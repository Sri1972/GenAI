package com.turboui.app.controller;

import com.turboui.app.service.TableService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api")
public class DynamicApiController {

    private final TableService tableService;

    public DynamicApiController(TableService tableService) {
        this.tableService = tableService;
    }

    @GetMapping("/tables")
    public ResponseEntity<Map<String, Object>> listTables() {
        Set<String> tables = tableService.listTables();
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("tables", tables);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/metadata")
    public ResponseEntity<Map<String, Object>> getMetadata() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("tables", tableService.getMetadata());
        return ResponseEntity.ok(response);
    }

    @GetMapping("/data/{table}")
    public ResponseEntity<?> getAll(
            @PathVariable String table,
            @RequestParam(required = false, defaultValue = "100") int limit,
            @RequestParam(required = false, defaultValue = "0") int offset,
            @RequestParam(required = false, defaultValue = "asc") String order,
            @RequestParam(required = false) String sort,
            @RequestParam(required = false) String filter,
            @RequestParam(required = false) Map<String, String> params) {
        try {
            // Remove known params from filter map
            params.remove("limit");
            params.remove("offset");
            params.remove("order");
            params.remove("sort");
            params.remove("filter");
            params.remove("page");
            params.remove("size");

            boolean hasFilter = (filter != null && !filter.isBlank()) || !params.isEmpty();
            int total = hasFilter ? tableService.count(table, filter, params) : tableService.count(table);
            List<Map<String, Object>> rows = hasFilter
                    ? tableService.query(table, filter, params, limit, offset, order)
                    : tableService.getAll(table, limit, offset, order);

            // Match Python template response format
            Map<String, Object> response = new LinkedHashMap<>();
            response.put("data", rows);
            response.put("total", total);
            response.put("limit", limit);
            response.put("offset", offset);
            response.put("hasMore", (offset + limit) < total);
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/data/{table}/count")
    public ResponseEntity<?> count(@PathVariable String table) {
        try {
            int count = tableService.count(table);
            return ResponseEntity.ok(Map.of("count", count));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/data/{table}/aggregate")
    public ResponseEntity<?> aggregate(
            @PathVariable String table,
            @RequestParam(required = false) String group_by,
            @RequestParam(required = false, defaultValue = "count") String agg) {
        try {
            List<Map<String, Object>> result = tableService.aggregate(table, group_by, agg);
            return ResponseEntity.ok(result);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/data/{table}/{id}")
    public ResponseEntity<?> getById(@PathVariable String table, @PathVariable String id) {
        try {
            Map<String, Object> row = tableService.getById(table, id);
            if (row == null) {
                return ResponseEntity.notFound().build();
            }
            return ResponseEntity.ok(row);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/data/{table}")
    public ResponseEntity<?> create(
            @PathVariable String table,
            @RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> created = tableService.insert(table, body);
            return ResponseEntity.status(201).body(created);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @PutMapping("/data/{table}/{id}")
    public ResponseEntity<?> update(
            @PathVariable String table,
            @PathVariable String id,
            @RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> updated = tableService.update(table, id, body);
            if (updated == null) {
                return ResponseEntity.notFound().build();
            }
            return ResponseEntity.ok(updated);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @DeleteMapping("/data/{table}/{id}")
    public ResponseEntity<?> delete(@PathVariable String table, @PathVariable String id) {
        try {
            boolean deleted = tableService.delete(table, id);
            if (!deleted) {
                return ResponseEntity.notFound().build();
            }
            return ResponseEntity.ok(Map.of("deleted", true));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }
}
