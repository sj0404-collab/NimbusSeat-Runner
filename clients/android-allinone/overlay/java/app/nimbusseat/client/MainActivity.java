package app.nimbusseat.client;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.limelight.PcView;

import org.json.JSONObject;

import java.util.Locale;

/**
 * NimbusSeat all-in-one launcher.
 *
 * Discovers the NimbusSeat host on the LAN, shows the 6-hour session
 * countdown, starts the session and opens the EMBEDDED Moonlight UI
 * (this very APK bundles the open-source moonlight-android streaming
 * core, GPL-3.0) - no extra downloads, no Play Market.
 */
public class MainActivity extends Activity {

    private final Handler ui = new Handler(Looper.getMainLooper());
    private volatile NimbusDiscovery.HostInfo host;
    private volatile NimbusApi api;

    private TextView hostName;
    private TextView stateText;
    private TextView timerText;
    private Button playButton;
    private Button stopButton;

    private final Runnable poll = new Runnable() {
        @Override
        public void run() {
            final NimbusApi a = api;
            if (a != null) {
                new Thread(() -> {
                    final JSONObject st = a.status();
                    if (st != null) ui.post(() -> render(st));
                    else ui.post(() -> stateText.setText("Нет связи с хостом"));
                }).start();
            }
            ui.postDelayed(this, 2000);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(Color.parseColor("#101418"));
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);

        hostName = text(root, 18, true, "Поиск хоста в локальной сети…");
        stateText = text(root, 14, false, "—");
        timerText = text(root, 40, true, "");
        timerText.setTextColor(Color.parseColor("#4FC3F7"));

        playButton = button(root, "▶  Играть");
        playButton.setEnabled(false);
        playButton.setOnClickListener(v -> play());

        stopButton = button(root, "⏹  Завершить сессию");
        stopButton.setEnabled(false);
        stopButton.setOnClickListener(v -> stopSession());

        Button moonlight = button(root, "🌙  Открыть Moonlight");
        moonlight.setOnClickListener(v -> startActivity(new Intent(this, PcView.class)));

        Button cloud = button(root, "☁  Облачное место (раннер)");
        cloud.setOnClickListener(v -> startActivity(new Intent(this, CloudSeatActivity.class)));

        Button rescan = button(root, "⟳  Обновить");
        rescan.setOnClickListener(v -> rescan());

        setContentView(root);
        rescan();
        ui.post(poll);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        ui.removeCallbacks(poll);
    }

    private TextView text(LinearLayout parent, int sp, boolean bold, String initial) {
        TextView t = new TextView(this);
        t.setTextSize(sp);
        t.setTextColor(Color.WHITE);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER);
        t.setText(initial);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = 16;
        parent.addView(t, lp);
        return t;
    }

    private Button button(LinearLayout parent, String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = 16;
        parent.addView(b, lp);
        return b;
    }

    private void rescan() {
        hostName.setText("Поиск хоста в локальной сети…");
        new Thread(() -> {
            NimbusDiscovery.HostInfo found = NimbusDiscovery.findHost(3000);
            ui.post(() -> {
                if (found != null) {
                    host = found;
                    api = new NimbusApi(found.ip, found.apiPort);
                    hostName.setText(found.name + " — " + found.ip);
                } else {
                    hostName.setText("Хост не найден. Проверьте Wi-Fi.");
                }
            });
        }).start();
    }

    private void render(JSONObject st) {
        String state = st.optString("state", "?");
        String human;
        switch (state) {
            case "idle":     human = "Свободен — можно играть"; break;
            case "active":   human = "Идёт сессия"; break;
            case "grace":    human = "Время вышло! Стрим завершается"; break;
            case "cooldown": human = "Перерыв между сессиями"; break;
            default:         human = state;
        }
        stateText.setText(human);
        long left = st.optLong("seconds_left", 0);
        timerText.setText("active".equals(state)
                ? String.format(Locale.US, "%d:%02d:%02d", left / 3600, (left % 3600) / 60, left % 60)
                : "");
        playButton.setEnabled("idle".equals(state));
        stopButton.setEnabled("active".equals(state));
    }

    private void play() {
        final NimbusApi a = api;
        if (a == null) return;
        new Thread(() -> {
            final JSONObject resp = a.startSession();
            ui.post(() -> {
                if (resp == null || !resp.optBoolean("ok")) {
                    Toast.makeText(this,
                            resp != null ? resp.optString("message", "Хост занят") : "Хост недоступен",
                            Toast.LENGTH_LONG).show();
                    return;
                }
                // Open the embedded Moonlight UI (bundled in this APK).
                startActivity(new Intent(this, PcView.class));
            });
        }).start();
    }

    private void stopSession() {
        final NimbusApi a = api;
        if (a == null) return;
        new Thread(a::stopSession).start();
    }
}
