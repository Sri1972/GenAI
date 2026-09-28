package com.api.security;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Shared usage.db access for RateLimitFilter, UsageTrackingFilter, and
 * UsageController — one place owning the schema and the rate-limit query, so
 * "how many requests has this client made" can never drift between what
 * decides allow/block and what GET /usage reports. Not LLM-generated: this
 * is infrastructure, not business logic.
 */
public final class UsageDb {

    private static final String DB_PATH = Path.of("usage.db").toAbsolutePath().toString();

    // Allowlist, not a blocklist — what counts toward being BLOCKED must be
    // the exact same thing counted in the "used" total GET /usage reports.
    // This platform's own architect prompt mandates business endpoints be
    // URL-versioned under /api/v1/ (api_architect's "API versioning
    // via URL path"), so anything else — favicon, health, docs, usage, the
    // root path, or any other infra/browser noise nobody thought to list —
    // is excluded by construction, not by trying to enumerate every possible
    // non-business path one at a time.
    public static final String RATE_LIMIT_PATH_PREFIX = "/api/";

    private UsageDb() {}

    public static Connection connect() throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:sqlite:" + DB_PATH);
        try (Statement st = conn.createStatement()) {
            st.execute("CREATE TABLE IF NOT EXISTS api_usage (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, client_id TEXT, " +
                    "method TEXT, path TEXT, status_code INTEGER, duration_ms REAL)");
            st.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_client_ts ON api_usage(client_id, ts)");
        }
        return conn;
    }

    public static boolean isBusinessPath(String uri) {
        return uri.startsWith(RATE_LIMIT_PATH_PREFIX);
    }

    /** {limit, windowSeconds, used, remaining} for this client — used by both
     * RateLimitFilter's allow/block decision and GET /usage's own report. */
    public static Map<String, Object> rateLimitStatus(String clientId, long windowSeconds) {
        int limit = Integer.parseInt(System.getenv().getOrDefault("RATE_LIMIT_RPM", "100"));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("limit", limit);
        result.put("windowSeconds", windowSeconds);
        if (limit <= 0) {
            result.put("used", 0L);
            result.put("remaining", null);
            return result;
        }

        double cutoff = System.currentTimeMillis() / 1000.0 - windowSeconds;

        long used = 0;
        try (Connection conn = connect();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT COUNT(*) FROM api_usage WHERE client_id = ? AND ts > ? AND path LIKE ?")) {
            ps.setString(1, clientId);
            ps.setDouble(2, cutoff);
            ps.setString(3, RATE_LIMIT_PATH_PREFIX + "%");
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) used = rs.getLong(1);
            }
        } catch (SQLException ignored) {
            // fail open — usage.db unreachable shouldn't block real traffic
        }

        result.put("used", used);
        result.put("remaining", Math.max(0, limit - used));
        return result;
    }
}
