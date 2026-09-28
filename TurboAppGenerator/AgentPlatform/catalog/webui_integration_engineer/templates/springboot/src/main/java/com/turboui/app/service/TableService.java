package com.turboui.app.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class TableService {

    private final JdbcTemplate jdbcTemplate;

    public TableService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Set<String> listTables() {
        List<String> tables = jdbcTemplate.queryForList(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
                String.class
        );
        return new LinkedHashSet<>(tables);
    }

    public List<Map<String, Object>> getAll(String table, int limit, int offset, String order) {
        validateTableName(table);
        String pkColumn = getPrimaryKeyColumn(table);
        String orderDir = "desc".equalsIgnoreCase(order) ? "DESC" : "ASC";
        String sql = String.format(
                "SELECT * FROM \"%s\" ORDER BY \"%s\" %s LIMIT ? OFFSET ?",
                table, pkColumn, orderDir
        );
        return jdbcTemplate.queryForList(sql, limit, offset);
    }

    public List<Map<String, Object>> query(String table, String filterStr, Map<String, String> filters, int limit, int offset, String order) {
        validateTableName(table);
        boolean hasFilterStr = filterStr != null && !filterStr.isBlank();
        boolean hasEquality = filters != null && !filters.isEmpty();
        if (!hasFilterStr && !hasEquality) {
            return getAll(table, limit, offset, order);
        }

        String pkColumn = getPrimaryKeyColumn(table);
        String orderDir = "desc".equalsIgnoreCase(order) ? "DESC" : "ASC";

        WhereClause where = buildWhereClause(filterStr, filters);
        if (where == null) {
            return getAll(table, limit, offset, order);
        }

        StringBuilder sql = new StringBuilder("SELECT * FROM \"").append(table).append("\" WHERE ").append(where.sql());
        List<Object> params = new ArrayList<>(where.params());

        sql.append(String.format(" ORDER BY \"%s\" %s LIMIT ? OFFSET ?", pkColumn, orderDir));
        params.add(limit);
        params.add(offset);

        return jdbcTemplate.queryForList(sql.toString(), params.toArray());
    }

    /** Count rows matching the same filter/filterStr combination used by query(). */
    public int count(String table, String filterStr, Map<String, String> filters) {
        validateTableName(table);
        WhereClause where = buildWhereClause(filterStr, filters);
        if (where == null) {
            return count(table);
        }
        String sql = "SELECT COUNT(*) FROM \"" + table + "\" WHERE " + where.sql();
        Integer c = jdbcTemplate.queryForObject(sql, Integer.class, where.params().toArray());
        return c != null ? c : 0;
    }

    /** column:operator:value, semicolon-separated. Mirrors the Python app_server_template's _parse_filter. */
    private static final Map<String, String> FILTER_OPS = Map.of(
            "eq", "=", "ne", "!=", "gt", ">", "lt", "<", "gte", ">=", "lte", "<="
    );

    private record WhereClause(String sql, List<Object> params) {}

    private WhereClause buildWhereClause(String filterStr, Map<String, String> equalityFilters) {
        StringBuilder sql = new StringBuilder();
        List<Object> params = new ArrayList<>();
        boolean first = true;

        if (filterStr != null && !filterStr.isBlank()) {
            for (String segment : filterStr.split(";")) {
                String[] parts = segment.split(":", 3);
                if (parts.length != 3) continue;
                String col = parts[0].replaceAll("[^a-zA-Z0-9_]", "");
                String op = parts[1];
                String val = parts[2];
                if (col.isEmpty()) continue;

                if ("in".equals(op)) {
                    String[] values = val.split(",");
                    if (values.length == 0) continue;
                    String placeholders = String.join(",", Collections.nCopies(values.length, "?"));
                    if (!first) sql.append(" AND ");
                    sql.append("\"").append(col).append("\" IN (").append(placeholders).append(")");
                    params.addAll(Arrays.asList((Object[]) values));
                    first = false;
                } else if ("like".equals(op)) {
                    if (!first) sql.append(" AND ");
                    sql.append("\"").append(col).append("\" LIKE ?");
                    params.add("%" + val + "%");
                    first = false;
                } else if (FILTER_OPS.containsKey(op)) {
                    if (!first) sql.append(" AND ");
                    sql.append("\"").append(col).append("\" ").append(FILTER_OPS.get(op)).append(" ?");
                    params.add(val);
                    first = false;
                }
                // unknown operator — skip this segment silently, matching Python's _parse_filter behavior
            }
        }

        if (equalityFilters != null) {
            for (Map.Entry<String, String> entry : equalityFilters.entrySet()) {
                if (!first) sql.append(" AND ");
                sql.append("\"").append(entry.getKey()).append("\" = ?");
                params.add(entry.getValue());
                first = false;
            }
        }

        return first ? null : new WhereClause(sql.toString(), params);
    }

    /** Table + column metadata for all tables — mirrors the Python app_server_template's /api/metadata shape. */
    public List<Map<String, Object>> getMetadata() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (String table : listTables()) {
            List<Map<String, Object>> columns = jdbcTemplate.queryForList("PRAGMA table_info(\"" + table + "\")");
            List<Map<String, Object>> schema = new ArrayList<>();
            for (Map<String, Object> col : columns) {
                Map<String, Object> c = new LinkedHashMap<>();
                c.put("name", col.get("name"));
                c.put("type", col.get("type"));
                c.put("pk", col.get("pk") != null && ((Number) col.get("pk")).intValue() > 0);
                Object notnull = col.get("notnull");
                c.put("nullable", !(notnull != null && ((Number) notnull).intValue() > 0));
                schema.add(c);
            }
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("table", table);
            entry.put("rowCount", count(table));
            entry.put("columns", schema);
            result.add(entry);
        }
        return result;
    }

    public Map<String, Object> getById(String table, Object id) {
        validateTableName(table);
        String pkColumn = getPrimaryKeyColumn(table);
        List<Map<String, Object>> results = jdbcTemplate.queryForList(
                "SELECT * FROM \"" + table + "\" WHERE \"" + pkColumn + "\" = ?", id
        );
        return results.isEmpty() ? null : results.get(0);
    }

    public Map<String, Object> insert(String table, Map<String, Object> data) {
        validateTableName(table);
        if (data == null || data.isEmpty()) {
            throw new IllegalArgumentException("No data provided for insert");
        }

        data = new LinkedHashMap<>(data);
        data.values().removeIf(Objects::isNull);

        StringBuilder sql = new StringBuilder("INSERT INTO \"").append(table).append("\" (");
        StringBuilder placeholders = new StringBuilder();
        List<Object> params = new ArrayList<>();

        boolean first = true;
        for (Map.Entry<String, Object> entry : data.entrySet()) {
            if (!first) {
                sql.append(", ");
                placeholders.append(", ");
            }
            sql.append("\"").append(entry.getKey()).append("\"");
            placeholders.append("?");
            params.add(entry.getValue());
            first = false;
        }

        sql.append(") VALUES (").append(placeholders).append(")");
        jdbcTemplate.update(sql.toString(), params.toArray());

        Integer lastId = jdbcTemplate.queryForObject("SELECT last_insert_rowid()", Integer.class);
        if (lastId != null) {
            return getById(table, lastId);
        }
        return data;
    }

    public Map<String, Object> update(String table, Object id, Map<String, Object> data) {
        validateTableName(table);
        String pkColumn = getPrimaryKeyColumn(table);

        if (data == null || data.isEmpty()) {
            return getById(table, id);
        }

        data = new LinkedHashMap<>(data);
        data.remove(pkColumn);

        StringBuilder sql = new StringBuilder("UPDATE \"").append(table).append("\" SET ");
        List<Object> params = new ArrayList<>();

        boolean first = true;
        for (Map.Entry<String, Object> entry : data.entrySet()) {
            if (!first) sql.append(", ");
            sql.append("\"").append(entry.getKey()).append("\" = ?");
            params.add(entry.getValue());
            first = false;
        }

        sql.append(" WHERE \"").append(pkColumn).append("\" = ?");
        params.add(id);
        jdbcTemplate.update(sql.toString(), params.toArray());

        return getById(table, id);
    }

    public boolean delete(String table, Object id) {
        validateTableName(table);
        String pkColumn = getPrimaryKeyColumn(table);
        int rows = jdbcTemplate.update(
                "DELETE FROM \"" + table + "\" WHERE \"" + pkColumn + "\" = ?", id
        );
        return rows > 0;
    }

    public int count(String table) {
        validateTableName(table);
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM \"" + table + "\"", Integer.class
        );
        return count != null ? count : 0;
    }

    public List<Map<String, Object>> aggregate(String table, String groupBy, String agg) {
        validateTableName(table);
        if (groupBy == null || groupBy.isBlank()) {
            int count = count(table);
            return List.of(Map.of("count", count));
        }

        String aggFn = switch (agg != null ? agg.toLowerCase() : "count") {
            case "sum" -> "SUM";
            case "avg" -> "AVG";
            case "min" -> "MIN";
            case "max" -> "MAX";
            default -> "COUNT";
        };

        String sql = String.format(
                "SELECT \"%s\", %s(*) as value FROM \"%s\" GROUP BY \"%s\" ORDER BY value DESC",
                groupBy, aggFn, table, groupBy
        );
        return jdbcTemplate.queryForList(sql);
    }

    private String getPrimaryKeyColumn(String table) {
        List<Map<String, Object>> columns = jdbcTemplate.queryForList(
                "PRAGMA table_info(\"" + table + "\")"
        );
        for (Map<String, Object> col : columns) {
            Object pk = col.get("pk");
            if (pk != null && ((Number) pk).intValue() > 0) {
                return (String) col.get("name");
            }
        }
        return "id";
    }

    private void validateTableName(String table) {
        if (table == null || !table.matches("^[a-zA-Z_][a-zA-Z0-9_]*$")) {
            throw new IllegalArgumentException("Invalid table name: " + table);
        }
        if (!listTables().contains(table)) {
            throw new IllegalArgumentException("Table not found: " + table);
        }
    }
}
