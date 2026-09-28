package com.turboui.app.controller;

import com.turboui.app.service.TableService;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import javax.net.ssl.*;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.KeyStore;
import java.util.*;

@RestController
@RequestMapping("/api")
public class ChatController {

    private final TableService tableService;
    private final String litellmBase;
    private final String litellmKey;
    private final String litellmModel;
    private final String litellmCert;

    public ChatController(TableService tableService) {
        this.tableService = tableService;
        this.litellmBase = env("LITELLM_API_BASE", "");
        this.litellmKey = env("LITELLM_API_KEY", "");
        this.litellmModel = env("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6");
        this.litellmCert = env("LITELLM_SSL_CERT", "");
    }

    private static String env(String key, String def) {
        String v = System.getenv(key);
        if (v != null && !v.isBlank()) return v;
        v = System.getProperty(key);
        return (v != null && !v.isBlank()) ? v : def;
    }

    @PostMapping("/chat")
    public ResponseEntity<?> chat(@RequestBody Map<String, Object> body) {
        if (litellmBase.isBlank() || litellmKey.isBlank()) {
            return ResponseEntity.status(503).body(Map.of(
                "error", "LLM not configured — set LITELLM_API_BASE and LITELLM_API_KEY environment variables"
            ));
        }

        try {
            @SuppressWarnings("unchecked")
            List<Map<String, String>> messages = (List<Map<String, String>>) body.get("messages");
            if (messages == null || messages.isEmpty()) {
                return ResponseEntity.badRequest().body(Map.of("error", "messages array is required"));
            }

            String dbContext = buildDatabaseContext();

            String systemPrompt = "You are an AI data analyst assistant. "
                + "Answer questions using the database context below. Be concise, use bullet points for summaries, "
                + "and include specific numbers when available.\n\n" + dbContext;

            List<Map<String, String>> fullMessages = new ArrayList<>();
            fullMessages.add(Map.of("role", "system", "content", systemPrompt));
            fullMessages.addAll(messages);

            Map<String, Object> llmRequest = new LinkedHashMap<>();
            llmRequest.put("model", litellmModel);
            llmRequest.put("messages", fullMessages);
            llmRequest.put("max_tokens", 4096);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("Authorization", "Bearer " + litellmKey);

            RestTemplate rest = buildRestTemplate();
            String url = litellmBase.replaceAll("/+$", "") + "/v1/chat/completions";

            ResponseEntity<Map> llmResponse = rest.exchange(
                url, HttpMethod.POST, new HttpEntity<>(llmRequest, headers), Map.class
            );

            if (llmResponse.getBody() == null) {
                return ResponseEntity.status(502).body(Map.of("error", "Empty response from LLM"));
            }

            @SuppressWarnings("unchecked")
            List<Map<String, Object>> choices = (List<Map<String, Object>>) llmResponse.getBody().get("choices");
            if (choices == null || choices.isEmpty()) {
                return ResponseEntity.status(502).body(Map.of("error", "No choices in LLM response"));
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
            String content = (String) message.get("content");

            Set<String> tables = tableService.listTables();
            List<String> sources = new ArrayList<>(tables);

            return ResponseEntity.ok(Map.of(
                "response", content,
                "type", "text",
                "sources", sources
            ));

        } catch (org.springframework.web.client.ResourceAccessException e) {
            System.err.println("[ChatController] LLM connectivity failed: " + e.getMessage());
            String hint = "LLM proxy unreachable at " + litellmBase
                + ". Check: (1) VPN/network connectivity, (2) LITELLM_API_BASE is correct, (3) LITELLM_SSL_CERT is valid.";
            return ResponseEntity.status(502).body(Map.of(
                "error", hint,
                "details", e.getMessage()
            ));
        } catch (org.springframework.web.client.HttpClientErrorException e) {
            System.err.println("[ChatController] LLM auth/client error: " + e.getStatusCode() + " " + e.getMessage());
            return ResponseEntity.status(502).body(Map.of(
                "error", "LLM returned " + e.getStatusCode() + ": check LITELLM_API_KEY and model name",
                "details", e.getResponseBodyAsString().substring(0, Math.min(500, e.getResponseBodyAsString().length()))
            ));
        } catch (Exception e) {
            System.err.println("[ChatController] LLM request failed: " + e.getClass().getName() + ": " + e.getMessage());
            e.printStackTrace(System.err);
            return ResponseEntity.status(502).body(Map.of(
                "error", "LLM request failed: " + e.getMessage(),
                "type", e.getClass().getSimpleName()
            ));
        }
    }

    @GetMapping("/chat/health")
    public ResponseEntity<?> chatHealth() {
        if (litellmBase.isBlank() || litellmKey.isBlank()) {
            return ResponseEntity.status(503).body(Map.of(
                "status", "not_configured",
                "error", "LITELLM_API_BASE and LITELLM_API_KEY not set"
            ));
        }
        try {
            RestTemplate rest = buildRestTemplate();
            String url = litellmBase.replaceAll("/+$", "") + "/health";
            ResponseEntity<String> resp = rest.getForEntity(url, String.class);
            return ResponseEntity.ok(Map.of(
                "status", "healthy",
                "litellm_base", litellmBase,
                "litellm_status", resp.getStatusCode().value()
            ));
        } catch (Exception e) {
            return ResponseEntity.status(502).body(Map.of(
                "status", "unreachable",
                "litellm_base", litellmBase,
                "error", e.getMessage()
            ));
        }
    }

    private String buildDatabaseContext() {
        StringBuilder sb = new StringBuilder("## Database Summary\n\n");
        try {
            Set<String> tables = tableService.listTables();
            for (String table : tables) {
                int count = tableService.count(table);
                sb.append("- **").append(table).append("**: ").append(count).append(" rows\n");
            }
            sb.append("\n## Sample Data\n\n");

            for (String table : tables) {
                List<Map<String, Object>> rows = tableService.getAll(table, 5, 0, "desc");
                if (!rows.isEmpty()) {
                    sb.append("### ").append(table).append(" (first 5 rows)\n");
                    sb.append("Columns: ").append(String.join(", ", rows.get(0).keySet())).append("\n");
                    for (Map<String, Object> row : rows) {
                        sb.append(row.values()).append("\n");
                    }
                    sb.append("\n");
                }
            }
        } catch (Exception e) {
            sb.append("(Could not load database context: ").append(e.getMessage()).append(")\n");
        }
        return sb.toString();
    }

    private RestTemplate buildRestTemplate() {
        try {
            // Parse the pinned cert (if provided) for direct-trust fallback
            final X509Certificate pinnedCert;
            if (!litellmCert.isBlank()) {
                String pem = litellmCert.replace("\\n", "\n");
                CertificateFactory cf = CertificateFactory.getInstance("X.509");
                pinnedCert = (X509Certificate) cf.generateCertificate(
                    new ByteArrayInputStream(pem.getBytes(StandardCharsets.UTF_8))
                );
            } else {
                pinnedCert = null;
            }

            // Try Windows certificate store (has corporate CAs that JRE cacerts lacks)
            X509TrustManager windowsTm = null;
            try {
                KeyStore winStore = KeyStore.getInstance("Windows-ROOT");
                winStore.load(null, null);
                TrustManagerFactory winTmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
                winTmf.init(winStore);
                for (TrustManager tm : winTmf.getTrustManagers()) {
                    if (tm instanceof X509TrustManager) { windowsTm = (X509TrustManager) tm; break; }
                }
            } catch (Exception ignored) {}

            // JRE default trust manager
            TrustManagerFactory defaultTmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            defaultTmf.init((KeyStore) null);
            X509TrustManager defaultTm = (X509TrustManager) defaultTmf.getTrustManagers()[0];

            final X509TrustManager finalWindowsTm = windowsTm;
            X509TrustManager combined = new X509TrustManager() {
                public void checkClientTrusted(X509Certificate[] chain, String authType) {}
                public void checkServerTrusted(X509Certificate[] chain, String authType) throws java.security.cert.CertificateException {
                    // 1. Try JRE default trust store
                    try { defaultTm.checkServerTrusted(chain, authType); return; } catch (Exception ignored) {}
                    // 2. Try Windows certificate store (has corporate SubCAs)
                    if (finalWindowsTm != null) {
                        try { finalWindowsTm.checkServerTrusted(chain, authType); return; } catch (Exception ignored) {}
                    }
                    // 3. Cert pinning: trust if server presents our known cert
                    if (pinnedCert != null) {
                        for (X509Certificate c : chain) {
                            if (c.equals(pinnedCert)) return;
                        }
                    }
                    throw new java.security.cert.CertificateException(
                        "Server certificate not trusted by JRE, Windows store, or pinned cert");
                }
                public X509Certificate[] getAcceptedIssuers() {
                    List<X509Certificate> all = new ArrayList<>(Arrays.asList(defaultTm.getAcceptedIssuers()));
                    if (finalWindowsTm != null) all.addAll(Arrays.asList(finalWindowsTm.getAcceptedIssuers()));
                    if (pinnedCert != null) all.add(pinnedCert);
                    return all.toArray(new X509Certificate[0]);
                }
            };

            SSLContext ctx = SSLContext.getInstance("TLS");
            ctx.init(null, new TrustManager[]{combined}, null);
            final SSLSocketFactory sslFactory = ctx.getSocketFactory();

            org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory() {
                    @Override
                    protected void prepareConnection(java.net.HttpURLConnection connection, String httpMethod) throws java.io.IOException {
                        if (connection instanceof javax.net.ssl.HttpsURLConnection) {
                            ((javax.net.ssl.HttpsURLConnection) connection).setSSLSocketFactory(sslFactory);
                        }
                        super.prepareConnection(connection, httpMethod);
                    }
                };
            factory.setConnectTimeout(10_000);
            factory.setReadTimeout(120_000);
            return new RestTemplate(factory);
        } catch (Exception e) {
            System.err.println("[ChatController] SSL setup failed, using default RestTemplate: " + e.getMessage());
            return new RestTemplate();
        }
    }
}
