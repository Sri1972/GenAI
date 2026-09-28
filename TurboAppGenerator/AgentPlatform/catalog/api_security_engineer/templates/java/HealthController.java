package com.api.security;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Deterministic /health endpoint — the LLM-generated app is instructed not to add
 * its own (a duplicate @GetMapping("/health") would crash Spring Boot's startup
 * with an ambiguous-mapping error). Also fixes a pre-existing gap where the
 * generated Dockerfile healthchecked /actuator/health without ever declaring the
 * actuator dependency.
 */
@RestController
public class HealthController {
    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }
}
