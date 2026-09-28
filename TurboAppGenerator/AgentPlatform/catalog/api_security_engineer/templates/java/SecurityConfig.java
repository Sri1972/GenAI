package com.api.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Deterministic Spring Security config. Not LLM-generated — auth must be correct
 * every generation. HTTP Basic when API_AUTH_TYPE=basic (reading credentials from
 * env, matching the Python template's basic_auth.py); otherwise permits all
 * (rate-limiting/usage-metering are separate filters, not gated by this class).
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.csrf(csrf -> csrf.disable());

        String authType = System.getenv().getOrDefault("API_AUTH_TYPE", "none");
        if ("basic".equals(authType)) {
            http.authorizeHttpRequests(auth -> auth
                            .requestMatchers("/health").permitAll()
                            .anyRequest().authenticated())
                    .httpBasic(basic -> {});
        } else {
            http.authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
        }
        return http.build();
    }

    @Bean
    public UserDetailsService userDetailsService() {
        String username = System.getenv().getOrDefault("API_BASIC_AUTH_USERNAME", "admin");
        String password = System.getenv().getOrDefault("API_BASIC_AUTH_PASSWORD", "changeme");
        return new InMemoryUserDetailsManager(
                User.withDefaultPasswordEncoder().username(username).password(password).roles("USER").build());
    }
}
