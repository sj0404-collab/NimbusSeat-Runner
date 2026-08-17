package app.nimbusseat.client

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * NimbusSeat Android client: discovers the host on the LAN, shows the
 * 6-hour session countdown and launches the Moonlight app to stream.
 */
class MainActivity : AppCompatActivity() {

    private var host: Discovery.HostInfo? = null
    private var api: NimbusApi? = null

    private lateinit var hostName: TextView
    private lateinit var stateText: TextView
    private lateinit var timerText: TextView
    private lateinit var playButton: MaterialButton
    private lateinit var stopButton: MaterialButton

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        hostName = findViewById(R.id.hostName)
        stateText = findViewById(R.id.stateText)
        timerText = findViewById(R.id.timerText)
        playButton = findViewById(R.id.playButton)
        stopButton = findViewById(R.id.stopButton)

        playButton.setOnClickListener { play() }
        stopButton.setOnClickListener { stopSession() }
        findViewById<MaterialButton>(R.id.rescanButton).setOnClickListener { rescan() }

        rescan()
        lifecycleScope.launch { pollLoop() }
    }

    private fun rescan() = lifecycleScope.launch {
        hostName.text = getString(R.string.searching)
        val found = Discovery.findHost()
        if (found != null) {
            host = found
            api = NimbusApi(found.ip, found.apiPort)
            hostName.text = "${found.name} — ${found.ip}"
        } else {
            hostName.text = "Хост не найден. Проверьте Wi-Fi."
        }
    }

    private suspend fun pollLoop() {
        while (true) {
            api?.status()?.let { render(it) }
            delay(2000)
        }
    }

    private fun render(st: org.json.JSONObject) {
        val state = st.optString("state", "?")
        stateText.text = when (state) {
            "idle" -> "Свободен — можно играть"
            "active" -> "Идёт сессия"
            "grace" -> "Время вышло! Стрим завершается"
            "cooldown" -> "Перерыв между сессиями"
            else -> state
        }
        val left = st.optLong("seconds_left", 0)
        timerText.text = if (state == "active") {
            "%d:%02d:%02d".format(left / 3600, (left % 3600) / 60, left % 60)
        } else ""
        playButton.isEnabled = state == "idle"
        stopButton.isEnabled = state == "active"
    }

    private fun play() = lifecycleScope.launch {
        val h = host ?: return@launch
        val resp = api?.startSession()
        if (resp == null || !resp.optBoolean("ok")) {
            Toast.makeText(
                this@MainActivity,
                resp?.optString("message") ?: "Хост недоступен",
                Toast.LENGTH_LONG
            ).show()
            return@launch
        }
        launchMoonlight(h.ip)
    }

    private fun stopSession() = lifecycleScope.launch {
        api?.stopSession()
    }

    /** Open the Moonlight app (or Play Market if it is not installed). */
    private fun launchMoonlight(hostIp: String) {
        val moonlight = packageManager.getLaunchIntentForPackage("com.limelight")
        if (moonlight != null) {
            startActivity(moonlight)
        } else {
            startActivity(
                Intent(
                    Intent.ACTION_VIEW,
                    Uri.parse("market://details?id=com.limelight")
                )
            )
        }
    }
}
