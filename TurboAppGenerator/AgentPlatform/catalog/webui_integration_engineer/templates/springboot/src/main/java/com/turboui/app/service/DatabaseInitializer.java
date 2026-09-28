package com.turboui.app.service;

import jakarta.annotation.PostConstruct;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class DatabaseInitializer {

    private final JdbcTemplate jdbcTemplate;

    public DatabaseInitializer(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @PostConstruct
    public void initialize() {
        initSchema();
        initSeed();
        applyVersionedMigrations();
    }

    private void initSchema() {
        Path schemaFile = Paths.get("schema.sql");
        if (!Files.exists(schemaFile)) {
            System.out.println("[db] No schema.sql found, skipping schema init");
            return;
        }

        try {
            String schemaSql = Files.readString(schemaFile);
            Set<String> existingTables = getExistingTables();

            if (existingTables.isEmpty()) {
                jdbcTemplate.execute("PRAGMA journal_mode=WAL");
                executeSqlStatements(schemaSql);
                System.out.println("[db] Schema initialized from schema.sql");
            } else {
                // Incremental: inject IF NOT EXISTS for safe re-runs
                String safeSql = Pattern.compile(
                        "CREATE\\s+TABLE\\s+(?!IF\\s+NOT\\s+EXISTS)",
                        Pattern.CASE_INSENSITIVE
                ).matcher(schemaSql).replaceAll("CREATE TABLE IF NOT EXISTS ");

                executeSqlStatements(safeSql);
                Set<String> newTables = getExistingTables();
                newTables.removeAll(existingTables);
                if (!newTables.isEmpty()) {
                    System.out.println("[db] Added new tables: " + String.join(", ", newTables));
                }
            }
        } catch (IOException e) {
            System.err.println("[db] Error reading schema.sql: " + e.getMessage());
        }
    }

    private void initSeed() {
        Path seedFile = Paths.get("seed.sql");
        if (!Files.exists(seedFile)) {
            return;
        }

        try {
            String seedSql = Files.readString(seedFile);

            // Replace null values with empty strings to avoid NOT NULL constraint failures
            seedSql = seedSql.replaceAll("(?i),null([,)])", ",''$1");
            seedSql = seedSql.replaceAll("(?i)\\(null,", "(''," );

            // Convert INSERT INTO to INSERT OR IGNORE for idempotent seeding
            seedSql = Pattern.compile(
                    "INSERT\\s+INTO",
                    Pattern.CASE_INSENSITIVE
            ).matcher(seedSql).replaceAll("INSERT OR IGNORE INTO");

            // Only seed tables that are empty
            Set<String> emptyTables = getEmptyTables();
            if (emptyTables.isEmpty()) {
                System.out.println("[db] All tables already have data, skipping seed");
                return;
            }

            // Filter seed statements to only empty tables
            String[] statements = seedSql.split(";");
            int seeded = 0;
            for (String stmt : statements) {
                String trimmed = stmt.trim();
                if (trimmed.isEmpty()) continue;

                Matcher m = Pattern.compile(
                        "INSERT\\s+(?:OR\\s+IGNORE\\s+)?INTO\\s+[\"']?(\\w+)[\"']?",
                        Pattern.CASE_INSENSITIVE
                ).matcher(trimmed);

                if (m.find()) {
                    String tableName = m.group(1);
                    if (emptyTables.contains(tableName)) {
                        try {
                            jdbcTemplate.execute(trimmed);
                            seeded++;
                        } catch (Exception e) {
                            System.err.println("[db] Seed warning for " + tableName + ": " + e.getMessage());
                        }
                    }
                }
            }
            if (seeded > 0) {
                System.out.println("[db] Seeded " + seeded + " statements into empty tables");
            }
        } catch (IOException e) {
            System.err.println("[db] Error reading seed.sql: " + e.getMessage());
        }
    }

    /**
     * Applies schema_v2.sql/seed_v2.sql (etc.) pairs from a refine's
     * incremental DB delta — see CrewOrchestrator._run_data_modeling_refine
     * on the Python generator side. Unlike v1's schema.sql above (safe to
     * re-run every startup via CREATE TABLE IF NOT EXISTS), these can
     * contain ALTER TABLE ADD COLUMN, which SQLite errors on if run twice —
     * so each version is tracked in _schema_migrations and applied exactly
     * once, ever. Uses executeSqlStatementsStrict (not executeSqlStatements)
     * deliberately: a migration that fails partway must NOT be recorded as
     * applied, so it can be retried next startup — the existing helper
     * swallows per-statement errors (right for v1's best-effort resilience),
     * which would silently mark a partially-failed migration as done.
     */
    private void applyVersionedMigrations() {
        jdbcTemplate.execute(
                "CREATE TABLE IF NOT EXISTS _schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)");
        Set<Integer> applied = new HashSet<>(
                jdbcTemplate.queryForList("SELECT version FROM _schema_migrations", Integer.class));

        List<Integer> versions = new java.util.ArrayList<>();
        Pattern versionPattern = Pattern.compile("schema_v(\\d+)\\.sql");
        try (java.util.stream.Stream<Path> files = Files.list(Paths.get("."))) {
            for (Path f : files.collect(java.util.stream.Collectors.toList())) {
                Matcher m = versionPattern.matcher(f.getFileName().toString());
                if (m.matches()) {
                    versions.add(Integer.parseInt(m.group(1)));
                }
            }
        } catch (IOException e) {
            System.err.println("[db] Error scanning for migration files: " + e.getMessage());
            return;
        }
        java.util.Collections.sort(versions);

        for (int version : versions) {
            if (applied.contains(version)) {
                continue;
            }
            Path schemaFile = Paths.get("schema_v" + version + ".sql");
            Path seedFile = Paths.get("seed_v" + version + ".sql");
            try {
                executeSqlStatementsStrict(Files.readString(schemaFile));
                if (Files.exists(seedFile)) {
                    String seedSql = Files.readString(seedFile);
                    seedSql = seedSql.replaceAll("(?i),null([,)])", ",''$1");
                    seedSql = seedSql.replaceAll("(?i)\\(null,", "(''," );
                    executeSqlStatementsStrict(seedSql);
                }
                jdbcTemplate.update(
                        "INSERT INTO _schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                        version);
                System.out.println("[db] Applied migration v" + version);
            } catch (Exception e) {
                System.err.println("[db] Migration v" + version + " failed, will retry next startup: " + e.getMessage());
            }
        }
    }

    private Set<String> getExistingTables() {
        List<String> tables = jdbcTemplate.queryForList(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
                String.class
        );
        return new HashSet<>(tables);
    }

    private Set<String> getEmptyTables() {
        Set<String> allTables = getExistingTables();
        Set<String> emptyTables = new HashSet<>();
        for (String table : allTables) {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM \"" + table + "\"", Integer.class);
            if (count != null && count == 0) {
                emptyTables.add(table);
            }
        }
        return emptyTables;
    }

    private void executeSqlStatements(String sql) {
        String[] statements = sql.split(";");
        for (String stmt : statements) {
            String trimmed = stmt.trim();
            if (!trimmed.isEmpty()) {
                try {
                    jdbcTemplate.execute(trimmed);
                } catch (Exception e) {
                    System.err.println("[db] Statement warning: " + e.getMessage());
                }
            }
        }
    }

    /** Same as executeSqlStatements, but propagates the first failure
     * instead of swallowing it — see applyVersionedMigrations for why. */
    private void executeSqlStatementsStrict(String sql) {
        String[] statements = sql.split(";");
        for (String stmt : statements) {
            String trimmed = stmt.trim();
            if (!trimmed.isEmpty()) {
                jdbcTemplate.execute(trimmed);
            }
        }
    }
}
