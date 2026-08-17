package app.nimbusseat.client

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Minimal REST client for the NimbusSeat host-manager API. */
class NimbusApi(private val ip: String, private val port: Int) {

    suspend fun status(): JSONObject? = request("status", "GET")
    suspend fun startSession(): JSONObject? = request("session/start", "POST")
    suspend fun stopSession(): JSONObject? = request("session/stop", "POST")

    private suspend fun request(path: String, method: String): JSONObject? =
        withContext(Dispatchers.IO) {
            try {
                val conn = URL("http://$ip:$port/api/v1/$path").openConnection() as HttpURLConnection
                conn.requestMethod = method
                conn.connectTimeout = 4000
                conn.readTimeout = 4000
                val stream = if (conn.responseCode < 400) conn.inputStream else conn.errorStream
                val body = stream.bufferedReader().use { it.readText() }
                JSONObject(body)
            } catch (_: Exception) {
                null
            }
        }
}
