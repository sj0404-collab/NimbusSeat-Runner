package app.nimbusseat.client

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

/** UDP LAN discovery of the NimbusSeat host (GeForce NOW style server list). */
object Discovery {
    private const val PORT = 48121
    private const val MAGIC = "NIMBUSSEAT/1"

    data class HostInfo(
        val ip: String,
        val name: String,
        val apiPort: Int,
        val state: String,
        val secondsLeft: Long,
    )

    suspend fun findHost(timeoutMs: Int = 3000): HostInfo? = withContext(Dispatchers.IO) {
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.soTimeout = timeoutMs
            val probe = MAGIC.toByteArray()
            socket.send(
                DatagramPacket(probe, probe.size, InetAddress.getByName("255.255.255.255"), PORT)
            )
            val buf = ByteArray(1024)
            val packet = DatagramPacket(buf, buf.size)
            return@withContext try {
                socket.receive(packet)
                val json = JSONObject(String(packet.data, 0, packet.length))
                if (json.optString("magic") != MAGIC) null
                else HostInfo(
                    ip = packet.address.hostAddress ?: return@withContext null,
                    name = json.optString("name", "NimbusSeat Host"),
                    apiPort = json.optInt("api_port", 48120),
                    state = json.optString("state", "unknown"),
                    secondsLeft = json.optLong("seconds_left", 0),
                )
            } catch (_: Exception) {
                null
            }
        }
    }
}
