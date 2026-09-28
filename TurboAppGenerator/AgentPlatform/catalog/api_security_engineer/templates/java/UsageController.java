package com.api.security;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Deterministic /usage endpoint — same aggregate shape as the Python template's
 * usage_router, backed by the same usage.db schema UsageDb owns (shared with
 * RateLimitFilter and UsageTrackingFilter).
 */
@RestController
public class UsageController {

    @GetMapping("/usage")
    public Map<String, Object> usage(HttpServletRequest request) throws Exception {
        try (Connection conn = UsageDb.connect();
             Statement st = conn.createStatement()) {
            Map<String, Object> result = new LinkedHashMap<>();

            long total = scalarLong(st, "SELECT COUNT(*) FROM api_usage");
            result.put("total_requests", total);

            double cutoff = System.currentTimeMillis() / 1000.0 - 86400;
            long last24h = scalarLong(st, "SELECT COUNT(*) FROM api_usage WHERE ts >= " + cutoff);
            result.put("requests_last_24h", last24h);

            long errors = scalarLong(st, "SELECT COUNT(*) FROM api_usage WHERE status_code >= 400");
            result.put("error_count", errors);
            result.put("error_rate", total > 0 ? Math.round((errors / (double) total) * 10000) / 10000.0 : 0.0);

            Map<String, Long> byEndpoint = new LinkedHashMap<>();
            try (ResultSet rs = st.executeQuery(
                    "SELECT path, COUNT(*) c FROM api_usage GROUP BY path ORDER BY c DESC LIMIT 20")) {
                while (rs.next()) byEndpoint.put(rs.getString(1), rs.getLong(2));
            }
            result.put("by_endpoint", byEndpoint);

            Map<String, Long> byClient = new LinkedHashMap<>();
            try (ResultSet rs = st.executeQuery(
                    "SELECT client_id, COUNT(*) c FROM api_usage GROUP BY client_id ORDER BY c DESC LIMIT 20")) {
                while (rs.next()) byClient.put(rs.getString(1), rs.getLong(2));
            }
            result.put("by_client", byClient);

            // Recent activity — method/path/status/timing only, never request/
            // response bodies (those aren't captured at all; see UsageTrackingFilter).
            List<Map<String, Object>> recent = new ArrayList<>();
            try (ResultSet rs = st.executeQuery(
                    "SELECT ts, client_id, method, path, status_code, duration_ms " +
                            "FROM api_usage ORDER BY id DESC LIMIT 20")) {
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("ts", rs.getDouble(1));
                    row.put("client_id", rs.getString(2));
                    row.put("method", rs.getString(3));
                    row.put("path", rs.getString(4));
                    row.put("status_code", rs.getInt(5));
                    row.put("duration_ms", Math.round(rs.getDouble(6) * 10) / 10.0);
                    recent.add(row);
                }
            }
            result.put("recent", recent);

            // The CALLING client's own current quota — piggybacks on this
            // already-happening request/response instead of a dedicated endpoint.
            result.put("rate_limit", UsageDb.rateLimitStatus(RateLimitFilter.extractClientId(request), 60));

            return result;
        }
    }

    /**
     * Wipes the usage log entirely — both the rate-limit counter and the
     * Total Requests/Recent Activity history, since they're now backed by
     * the same table on purpose (see UsageDb.rateLimitStatus). A dev/test
     * convenience, not a production audit feature: a real system would
     * never want to lose this history, but restarting used to give an easy
     * "start clean" reset before the rate limiter moved off in-memory
     * state, and this is that same convenience back. Not itself
     * rate-limited (path doesn't start with /api/) — still requires valid
     * Basic Auth if auth_type=basic, same as every other non-business route.
     */
    @PostMapping("/usage/reset")
    public Map<String, Object> resetUsage() throws Exception {
        try (Connection conn = UsageDb.connect();
             Statement st = conn.createStatement()) {
            st.execute("DELETE FROM api_usage");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("reset", true);
        return result;
    }

    private long scalarLong(Statement st, String sql) throws Exception {
        try (ResultSet rs = st.executeQuery(sql)) {
            return rs.next() ? rs.getLong(1) : 0;
        }
    }
}
