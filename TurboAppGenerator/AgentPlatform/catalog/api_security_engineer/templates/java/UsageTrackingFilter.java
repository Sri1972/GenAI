package com.api.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.boot.autoconfigure.security.SecurityProperties;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;

/**
 * Deterministic usage-metering filter — logs every request to a local SQLite
 * usage.db (schema owned by UsageDb, shared with RateLimitFilter and
 * UsageController). Not LLM-generated: metering must be present on every
 * generation.
 *
 * @Order places this before RateLimitFilter and Spring Security's chain, so it's
 * the outermost filter and always records the final status code (401/429/2xx/etc).
 */
@Component
@Order(SecurityProperties.DEFAULT_FILTER_ORDER - 10)
public class UsageTrackingFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        long start = System.nanoTime();
        chain.doFilter(request, response);
        double durationMs = (System.nanoTime() - start) / 1_000_000.0;

        try (Connection conn = UsageDb.connect();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO api_usage (ts, client_id, method, path, status_code, duration_ms) " +
                             "VALUES (?, ?, ?, ?, ?, ?)")) {
            ps.setDouble(1, System.currentTimeMillis() / 1000.0);
            ps.setString(2, RateLimitFilter.extractClientId(request));
            ps.setString(3, request.getMethod());
            ps.setString(4, request.getRequestURI());
            ps.setInt(5, response.getStatus());
            ps.setDouble(6, durationMs);
            ps.executeUpdate();
        } catch (SQLException ignored) {
            // usage logging must never break the actual request
        }
    }
}
