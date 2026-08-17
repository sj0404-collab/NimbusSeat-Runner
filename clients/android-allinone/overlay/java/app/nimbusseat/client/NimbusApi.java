package app.nimbusseat.client;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/** Minimal REST client for the NimbusSeat host-manager API. Blocking; use from background threads. */
public final class NimbusApi {
    private final String ip;
    private final int port;

    public NimbusApi(String ip, int port) {
        this.ip = ip;
        this.port = port;
    }

    public JSONObject status()       { return request("status", "GET"); }
    public JSONObject startSession() { return request("session/start", "POST"); }
    public JSONObject stopSession()  { return request("session/stop", "POST"); }

    private JSONObject request(String path, String method) {
        try {
            HttpURLConnection conn = (HttpURLConnection)
                    new URL("http://" + ip + ":" + port + "/api/v1/" + path).openConnection();
            conn.setRequestMethod(method);
            conn.setConnectTimeout(4000);
            conn.setReadTimeout(4000);
            InputStream stream = conn.getResponseCode() < 400
                    ? conn.getInputStream() : conn.getErrorStream();
            StringBuilder sb = new StringBuilder();
            try (BufferedReader r = new BufferedReader(new InputStreamReader(stream))) {
                String line;
                while ((line = r.readLine()) != null) sb.append(line);
            }
            return new JSONObject(sb.toString());
        } catch (Exception e) {
            return null;
        }
    }
}
