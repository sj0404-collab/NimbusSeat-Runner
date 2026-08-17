package app.nimbusseat.client;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Cloud seat: controls the GitHub-runner-based remote desktop and connects
 * to it inside an embedded WebView (nimbus.html with touch gamepad,
 * BT/OTG passthrough, virtual keyboard and quality settings).
 *
 * The GitHub repo and token are user-configurable and stored locally, so the
 * app keeps working even if the original account/repo is gone - just point
 * it at a new mirror (docs/MIGRATION.md).
 */
public class CloudSeatActivity extends Activity {

    private static final String PREFS = "nimbus_cloud";
    private SharedPreferences prefs;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private TextView status;
    private WebView web;
    private LinearLayout controls;
    private String liveUrl = null;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#0d0f13"));

        controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.VERTICAL);
        controls.setGravity(Gravity.CENTER);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        controls.setPadding(pad, pad, pad, pad);

        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(15);
        status.setGravity(Gravity.CENTER);
        status.setText("Облачное место (GitHub-раннер)");
        controls.addView(status, lp());

        Button start = btn("▶ Запустить раннер");
        start.setOnClickListener(v -> dispatchRunner());
        controls.addView(start, lp());

        Button connect = btn("🔗 Подключиться");
        connect.setOnClickListener(v -> fetchSession(true));
        controls.addView(connect, lp());

        Button stop = btn("⏹ Остановить раннер");
        stop.setOnClickListener(v -> stopRunner());
        controls.addView(stop, lp());

        Button cfg = btn("⚙ Repo / токен");
        cfg.setOnClickListener(v -> showConfig());
        controls.addView(cfg, lp());

        root.addView(controls, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 0));

        web = new WebView(this);
        configureWeb();
        LinearLayout.LayoutParams wlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1);
        root.addView(web, wlp);

        setContentView(root);
        fetchSession(false);   // авто: если сессия уже live — сразу покажем
    }

    private LinearLayout.LayoutParams lp() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        p.topMargin = 12;
        return p;
    }

    private Button btn(String t) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        return b;
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWeb() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        web.setBackgroundColor(Color.BLACK);
        web.setWebViewClient(new WebViewClient());
    }

    private String repo()  { return prefs.getString("repo", "sj0404-collab/NimbusSeat-Runner"); }
    private String token() { return prefs.getString("token", ""); }

    private void showConfig() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int p = (int) (16 * getResources().getDisplayMetrics().density);
        box.setPadding(p, p, p, p);
        EditText r = new EditText(this);
        r.setHint("owner/repo");
        r.setText(repo());
        EditText t = new EditText(this);
        t.setHint("GitHub token (fine-grained: Actions RW, Contents R)");
        t.setText(token());
        t.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        box.addView(r); box.addView(t);
        new AlertDialog.Builder(this)
                .setTitle("Настройки облака")
                .setMessage("Если аккаунт GitHub закроется — укажите новое зеркало и новый токен (см. docs/MIGRATION.md)")
                .setView(box)
                .setPositiveButton("Сохранить", (d, w) ->
                        prefs.edit().putString("repo", r.getText().toString().trim())
                                .putString("token", t.getText().toString().trim()).apply())
                .setNegativeButton("Отмена", null)
                .show();
    }

    /* ---------------- GitHub API ---------------- */

    private JSONObject gh(String method, String path, JSONObject body) {
        try {
            HttpURLConnection c = (HttpURLConnection)
                    new URL("https://api.github.com" + path).openConnection();
            c.setRequestMethod(method);
            c.setRequestProperty("Authorization", "token " + token());
            c.setRequestProperty("Accept", "application/vnd.github+json");
            c.setConnectTimeout(10000);
            c.setReadTimeout(10000);
            if (body != null) {
                c.setDoOutput(true);
                try (OutputStream os = c.getOutputStream()) {
                    os.write(body.toString().getBytes());
                }
            }
            int code = c.getResponseCode();
            InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream();
            StringBuilder sb = new StringBuilder();
            if (in != null) {
                try (BufferedReader br = new BufferedReader(new InputStreamReader(in))) {
                    String l; while ((l = br.readLine()) != null) sb.append(l);
                }
            }
            JSONObject res = sb.length() > 0 ? new JSONObject(sb.toString()) : new JSONObject();
            res.put("_http", code);
            return res;
        } catch (Exception e) {
            return null;
        }
    }

    private void dispatchRunner() {
        if (token().isEmpty()) { showConfig(); return; }
        status.setText("Запускаю раннер…");
        new Thread(() -> {
            JSONObject body = new JSONObject();
            try {
                body.put("ref", "main");
                JSONObject inputs = new JSONObject();
                inputs.put("minutes", "340");
                body.put("inputs", inputs);
            } catch (Exception ignored) {}
            JSONObject r = gh("POST",
                    "/repos/" + repo() + "/actions/workflows/remote-seat.yml/dispatches", body);
            boolean ok = r != null && r.optInt("_http") == 204;
            ui.post(() -> status.setText(ok
                    ? "Раннер запускается (1-3 мин). Жмите «Подключиться»…"
                    : "Ошибка запуска: проверьте repo/токен"));
            if (ok) pollUntilLive();
        }).start();
    }

    private void stopRunner() {
        if (token().isEmpty()) { showConfig(); return; }
        new Thread(() -> {
            JSONObject runs = gh("GET", "/repos/" + repo() + "/actions/runs?per_page=10", null);
            if (runs == null) return;
            try {
                var arr = runs.getJSONArray("workflow_runs");
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject run = arr.getJSONObject(i);
                    String st = run.optString("status");
                    if (run.optString("name").startsWith("Remote Seat")
                            && (st.equals("queued") || st.equals("in_progress"))) {
                        gh("POST", "/repos/" + repo() + "/actions/runs/" + run.getLong("id") + "/cancel", new JSONObject());
                    }
                }
                ui.post(() -> { status.setText("Остановка отправлена"); web.loadUrl("about:blank"); });
            } catch (Exception ignored) {}
        }).start();
    }

    private void pollUntilLive() {
        new Thread(() -> {
            String prev = liveUrl;
            for (int i = 0; i < 40; i++) {
                try { Thread.sleep(10000); } catch (InterruptedException e) { return; }
                JSONObject s = readSession();
                if (s != null && "live".equals(s.optString("state"))
                        && !s.optString("url").equals(prev)) {
                    final String url = s.optString("url");
                    liveUrl = url;
                    ui.post(() -> { status.setText("✅ Подключено — ПК активирован"); web.loadUrl(url); });
                    return;
                }
            }
            ui.post(() -> status.setText("Таймаут — проверьте Actions в репозитории"));
        }).start();
    }

    /** session.json из ветки live — там ссылка уже с паролем: ничего вводить не нужно. */
    private JSONObject readSession() {
        JSONObject r = gh("GET", "/repos/" + repo() + "/contents/session.json?ref=live", null);
        if (r == null || !r.has("content")) return null;
        try {
            String json = new String(Base64.decode(r.getString("content"), Base64.DEFAULT));
            return new JSONObject(json);
        } catch (Exception e) {
            return null;
        }
    }

    private void fetchSession(boolean loud) {
        new Thread(() -> {
            JSONObject s = readSession();
            ui.post(() -> {
                if (s != null && "live".equals(s.optString("state"))) {
                    liveUrl = s.optString("url");
                    status.setText("✅ Сессия live: " + s.optString("resolution")
                            + " @ " + s.optInt("fps") + "fps");
                    web.loadUrl(liveUrl);
                } else if (loud) {
                    Toast.makeText(this, "Сессия не запущена — нажмите «Запустить раннер»",
                            Toast.LENGTH_LONG).show();
                }
            });
        }).start();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
}
