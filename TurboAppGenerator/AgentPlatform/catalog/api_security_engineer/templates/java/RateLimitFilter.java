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
import java.util.Base64;
import java.util.Map;

/**
 * Deterministic rate-limiting filter — backed by the same usage.db every
 * request is already logged to (see UsageTrackingFilter), not a separate
 * in-memory counter (see UsageDb for the shared query/exemption logic). One
 * source of truth for "how many requests has this client made" — the same
 * data GET /usage reports — and the limit naturally survives restarts
 * instead of silently resetting.
 *
 * Adds X-RateLimit-Limit / X-RateLimit-Remaining response headers on every
 * call (success or 429) — visible in Swagger UI's own response viewer and to
 * any real client, with no separate call needed to see it.
 *
 * Not LLM-generated: throttling must behave identically every generation.
 *
 * @Component + OncePerRequestFilter is auto-registered by Spring Boot's servlet
 * filter auto-configuration — no manual wiring in Application.java needed.
 * @Order places this just before Spring Security's chain (DEFAULT_FILTER_ORDER),
 * so a rate-limited request never even reaches auth checks.
 */
@Component
@Order(SecurityProperties.DEFAULT_FILTER_ORDER - 5)
public class RateLimitFilter extends OncePerRequestFilter {

    private static final long WINDOW_SECONDS = 60;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (!UsageDb.isBusinessPath(request.getRequestURI())) {
            chain.doFilter(request, response);
            return;
        }

        String clientId = extractClientId(request);
        Map<String, Object> status = UsageDb.rateLimitStatus(clientId, WINDOW_SECONDS);
        int limit = ((Number) status.get("limit")).intValue();
        if (limit <= 0) {
            chain.doFilter(request, response);
            return;
        }

        long used = ((Number) status.get("used")).longValue();
        if (used >= limit) {
            response.setStatus(429);
            response.setHeader("Retry-After", String.valueOf(WINDOW_SECONDS));
            response.setHeader("X-RateLimit-Limit", String.valueOf(limit));
            response.setHeader("X-RateLimit-Remaining", "0");
            response.setContentType("application/json");
            response.getWriter().write("{\"detail\":\"Rate limit exceeded\"}");
            return;
        }

        // This request isn't logged to api_usage until AFTER it completes (see
        // UsageTrackingFilter, the outermost filter), so `used` above reflects
        // requests before this one — knock one more off the reported remaining
        // count for the request currently in flight, once it succeeds. Headers
        // must be set BEFORE chain.doFilter() commits the response.
        long remaining = ((Number) status.get("remaining")).longValue();
        response.setHeader("X-RateLimit-Limit", String.valueOf(limit));
        response.setHeader("X-RateLimit-Remaining", String.valueOf(Math.max(0, remaining - 1)));
        chain.doFilter(request, response);
    }

    static String extractClientId(HttpServletRequest request) {
        String auth = request.getHeader("Authorization");
        if (auth != null && auth.toLowerCase().startsWith("basic ")) {
            try {
                String decoded = new String(Base64.getDecoder().decode(auth.substring(6)));
                return "user:" + decoded.split(":", 2)[0];
            } catch (Exception ignored) {
                // fall through to IP-based id
            }
        }
        return "ip:" + request.getRemoteAddr();
    }
}
