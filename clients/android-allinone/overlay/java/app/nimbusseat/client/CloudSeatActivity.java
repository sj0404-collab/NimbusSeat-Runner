package app.nimbusseat.client;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebChromeClient;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
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
 * Cloud seat: controls a GitHub-runner-based remote desktop and connects to it
 * inside an embedded WebView (nimbus.html with touch gamepad, BT/OTG
 * passthrough, virtual keyboard and quality settings).
 *
 * The target is data, not a hardcoded repo: repo + token + workflow + where the
 * live session descriptor lives. That is what lets one app point at ANY repo
 * and runner - its own NimbusSeat-Runner, a `zen-panel` screen, a fork, a
 * mirror (see docs/MIGRATION.md) - and it keeps working if the account moves.
 *
 * Two session layouts are understood without any extra wiring:
 *   NimbusSeat  branch `live`,          file `session.json`     url = nimbus.html
 *   zen-panel   branch `session-state`, file `live/session-vnc.json` url = vnc.html
 * The address is taken from url / novncUrl / novnc / web; the state falls back
 * to "live when an address is present".
 */
public class CloudSeatActivity extends Activity {

    private static final String PREFS = "nimbus_cloud";
    private static final String[] URL_KEYS = {"url", "novncUrl", "novnc", "web", "desktop", "hubUrl"};

    private SharedPreferences prefs;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private TextView status;
    private WebView web;
    private View stage;
    private View previewOverlay;
    private LinearLayout controls;
    private View controlsPane;
    private LinearLayout.LayoutParams webLp;
    private int previewHeightPx;
    private boolean controlsExpanded = true;
    private String liveUrl = null;

    /**
     * Show/hide the control panel. Panel visible => the stream sits in a short
     * preview box (tap it to expand); hidden => stream is fullscreen.
     */
    private void setPanel(boolean preview) {
        controlsExpanded = preview;
        controlsPane.setVisibility(preview ? View.VISIBLE : View.GONE);
        previewOverlay.setVisibility(preview && liveUrl != null ? View.VISIBLE : View.GONE);
        if (webLp != null && stage != null) {
            webLp.height = preview ? previewHeightPx : 0;
            webLp.weight = preview ? 0f : 1f;
            stage.setLayoutParams(webLp);
        }
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
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
        status.setText("Облачное место. Кнопка Назад показывает/прячет эту панель.");
        controls.addView(status, lp());

        Button start = btn("▶ Запустить раннер");
        start.setOnClickListener(v -> dispatchRunner());
        controls.addView(start, lp());

        Button preview = btn("🔗 Предпросмотр");
        preview.setOnClickListener(v -> connect(false, false));
        controls.addView(preview, lp());

        Button full = btn("⛶ На весь экран");
        full.setOnClickListener(v -> connect(true, false));
        controls.addView(full, lp());

        Button link = btn("↗ Ссылка в браузере");
        link.setOnClickListener(v -> openExternal());
        controls.addView(link, lp());

        Button stop = btn("⏹ Остановить раннер");
        stop.setOnClickListener(v -> stopRunner());
        controls.addView(stop, lp());

        Button cfg = btn("⚙ Репо / workflow / сессия");
        cfg.setOnClickListener(v -> showConfig());
        controls.addView(cfg, lp());

        web = new WebView(this);
        configureWeb();

        previewOverlay = new View(this);
        previewOverlay.setBackgroundColor(Color.TRANSPARENT);
        previewOverlay.setVisibility(View.GONE);
        previewOverlay.setOnClickListener(v -> setPanel(false));

        FrameLayout stageBox = new FrameLayout(this);
        stageBox.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        stageBox.addView(previewOverlay, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        stage = stageBox;

        previewHeightPx = (int) (getResources().getDisplayMetrics().heightPixels * 0.45f);
        webLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, previewHeightPx);
        root.addView(stage, webLp);

        android.widget.ScrollView panel = new android.widget.ScrollView(this);
        panel.addView(controls, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        controlsPane = panel;
        root.addView(controlsPane, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);
        connect(true, true);   // авто: если сессия уже live — сразу покажем
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
        web.setWebChromeClient(new WebChromeClient());
    }

    /* ---------------- target configuration ---------------- */

    private String repo()       { return prefs.getString("repo", "sj0404-collab/NimbusSeat-Runner"); }
    private String token()      { return prefs.getString("token", ""); }
    private String workflow()   { return prefs.getString("workflow", "remote-seat.yml"); }
    private String branch()     { return prefs.getString("session_branch", "live"); }
    private String sessionPath(){ return prefs.getString("session_path", "session.json"); }
    private String inputs()     { return prefs.getString("inputs", "{\"minutes\":\"340\"}"); }

    private void showConfig() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int p = (int) (16 * getResources().getDisplayMetrics().density);
        box.setPadding(p, p, p, p);

        // Presets flip the whole target in one tap; everything stays editable.
        LinearLayout presets = new LinearLayout(this);
        presets.setOrientation(LinearLayout.HORIZONTAL);
        Button nimbus = new Button(this);
        nimbus.setText("NimbusSeat");
        nimbus.setAllCaps(false);
        Button zen = new Button(this);
        zen.setText("zen-panel экран");
        zen.setAllCaps(false);
        presets.addView(nimbus);
        presets.addView(zen);
        box.addView(presets);

        EditText r = field(box, "owner/repo", repo());
        EditText t = new EditText(this);
        t.setHint("GitHub token (fine-grained: Actions RW, Contents R)");
        t.setText(token());
        t.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        box.addView(t);
        EditText wf = field(box, "workflow file (e.g. remote-seat.yml / hub.yml)", workflow());
        EditText br = field(box, "session branch (live / session-state)", branch());
        EditText sp = field(box, "session file (session.json / live/session-vnc.json)", sessionPath());
        EditText in = field(box, "dispatch inputs (JSON)", inputs());

        nimbus.setOnClickListener(v -> {
            r.setText("sj0404-collab/NimbusSeat-Runner");
            wf.setText("remote-seat.yml");
            br.setText("live");
            sp.setText("session.json");
            in.setText("{\"minutes\":\"340\"}");
        });
        zen.setOnClickListener(v -> {
            r.setText("sj0404-collab/zen-panel");
            wf.setText("hub.yml");
            br.setText("session-state");
            sp.setText("live/session-vnc.json");
            in.setText("{\"os\":\"linux\",\"label\":\"panel\"}");
        });

        new AlertDialog.Builder(this)
                .setTitle("Настройки облака (цель)")
                .setMessage("Репо + workflow + откуда брать живую сессию. Так один клиент "
                        + "подключается к любому репо/раннеру (docs/MIGRATION.md).")
                .setView(box)
                .setPositiveButton("Сохранить", (d, wd) ->
                        prefs.edit()
                                .putString("repo", r.getText().toString().trim())
                                .putString("token", t.getText().toString().trim())
                                .putString("workflow", wf.getText().toString().trim())
                                .putString("session_branch", br.getText().toString().trim())
                                .putString("session_path", sp.getText().toString().trim())
                                .putString("inputs", in.getText().toString().trim())
                                .apply())
                .setNegativeButton("Отмена", null)
                .show();
    }

    private EditText field(LinearLayout parent, String hint, String value) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setInputType(InputType.TYPE_CLASS_TEXT);
        parent.addView(e);
        return e;
    }

    /* ---------------- GitHub API ---------------- */

    private JSONObject gh(String method, String path, JSONObject body) {
        try {
            HttpURLConnection c = (HttpURLConnection)
                    new URL("https://api.github.com" + path).openConnection();
            c.setRequestMethod(method);
            // A bare `Authorization: token ` makes GitHub reject even public
            // repos with 401, so only authenticate when a token is present.
            if (!token().isEmpty()) {
                c.setRequestProperty("Authorization", "token " + token());
            }
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
                body.put("inputs", new JSONObject(inputs()));
            } catch (Exception ignored) {}
            JSONObject r = gh("POST",
                    "/repos/" + repo() + "/actions/workflows/" + workflow() + "/dispatches", body);
            boolean ok = r != null && r.optInt("_http") == 204;
            ui.post(() -> status.setText(ok
                    ? "Раннер запускается (1-3 мин). Жмите «Предпросмотр»…"
                    : "Ошибка запуска: проверьте repo/workflow/токен"));
            if (ok) pollUntilLive();
        }).start();
    }

    private void stopRunner() {
        if (token().isEmpty()) { showConfig(); return; }
        new Thread(() -> {
            JSONObject runs = gh("GET", "/repos/" + repo() + "/actions/runs?per_page=20", null);
            if (runs == null) return;
            try {
                var arr = runs.getJSONArray("workflow_runs");
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject run = arr.getJSONObject(i);
                    String st = run.optString("status");
                    boolean active = st.equals("queued") || st.equals("in_progress");
                    // Match by workflow path so it works for any target, not a name.
                    boolean mine = run.optString("path").endsWith("/" + workflow());
                    if (active && mine) {
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
                String url = urlOf(s);
                if (s != null && isLive(s) && url != null && !url.equals(prev)) {
                    liveUrl = decorateNovnc(url);
                    ui.post(() -> { status.setText("✅ Подключено — ПК активирован");
                        web.loadUrl(liveUrl); setPanel(false); });
                    return;
                }
            }
            ui.post(() -> status.setText("Таймаут — проверьте Actions в репозитории"));
        }).start();
    }

    /** True when the descriptor says live (or says nothing but carries an address). */
    private boolean isLive(JSONObject s) {
        if (s == null) return false;
        String state = s.optString("state", "");
        if (!state.isEmpty()) return "live".equals(state);
        return urlOf(s) != null;
    }

    private String urlOf(JSONObject s) {
        if (s == null) return null;
        for (String key : URL_KEYS) {
            String v = s.optString(key, "");
            if (v.startsWith("http://") || v.startsWith("https://")) return v;
        }
        return null;
    }

    /**
     * A bare noVNC page stops on a dark "Connect" dialog and renders the remote
     * 1:1 (on a phone: one dark corner) unless told to autoconnect and fit. Add
     * both for a noVNC page that carries no query of its own.
     */
    private String decorateNovnc(String u) {
        if (u == null) return null;
        if (!u.contains("vnc.html") && !u.contains("vnc_lite.html")) return u;
        if (u.contains("autoconnect=")) return u;
        return u + (u.contains("?") ? "&" : "?") + "autoconnect=1&resize=scale";
    }

    /** The live descriptor from the target's branch/path - address already inside. */
    private JSONObject readSession() {
        JSONObject r = gh("GET",
                "/repos/" + repo() + "/contents/" + sessionPath() + "?ref=" + branch(), null);
        if (r == null || !r.has("content")) return null;
        try {
            String json = new String(Base64.decode(r.getString("content"), Base64.DEFAULT));
            return new JSONObject(json);
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * Read the live descriptor and embed it in the preview (or fullscreen).
     * Never reports "runner off" while an address is actually present: some
     * publishers carry only a URL, without a `state`.
     */
    private void connect(boolean fullScreen, boolean quiet) {
        new Thread(() -> {
            JSONObject s = readSession();
            final String url = urlOf(s);
            final String state = s == null ? "" : s.optString("state", "");
            ui.post(() -> {
                if (url != null) {
                    liveUrl = decorateNovnc(url);
                    status.setText(state.isEmpty() || "live".equals(state)
                            ? "✅ Сессия live"
                            : "⚠️ Сессия: " + state);
                    web.loadUrl(liveUrl);
                    setPanel(!fullScreen);
                } else {
                    status.setText("Адреса сессии нет — запустите раннер или проверьте цель");
                    if (!quiet) {
                        Toast.makeText(this,
                                "Нет адреса сессии. Проверьте repo/branch/path и токен",
                                Toast.LENGTH_LONG).show();
                    }
                }
            });
        }).start();
    }

    private void openExternal() {
        if (liveUrl == null) {
            Toast.makeText(this, "Сначала подключитесь", Toast.LENGTH_SHORT).show();
            return;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(liveUrl)));
        } catch (Exception e) {
            Toast.makeText(this, "Нет браузера", Toast.LENGTH_SHORT).show();
        }
    }

    private long lastBack = 0;

    @Override
    public void onBackPressed() {
        // Первое нажатие «Назад» — переключить панель управления,
        // быстрое двойное — выйти из активности.
        long now = System.currentTimeMillis();
        if (now - lastBack < 1500) {
            super.onBackPressed();
            return;
        }
        lastBack = now;
        setPanel(!controlsExpanded);
        Toast.makeText(this, controlsExpanded
                ? "Панель показана. Двойное «Назад» — выход"
                : "Стрим на весь экран. «Назад» — панель", Toast.LENGTH_SHORT).show();
    }
}
