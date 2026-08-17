package app.nimbusseat.client;

import org.json.JSONObject;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;

/** UDP LAN discovery of the NimbusSeat host (GeForce NOW style server list). */
public final class NimbusDiscovery {
    public static final int PORT = 48121;
    public static final String MAGIC = "NIMBUSSEAT/1";

    public static final class HostInfo {
        public final String ip;
        public final String name;
        public final int apiPort;

        HostInfo(String ip, String name, int apiPort) {
            this.ip = ip;
            this.name = name;
            this.apiPort = apiPort;
        }
    }

    private NimbusDiscovery() {}

    /** Blocking; call from a background thread. */
    public static HostInfo findHost(int timeoutMs) {
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.setBroadcast(true);
            socket.setSoTimeout(timeoutMs);
            byte[] probe = MAGIC.getBytes();
            socket.send(new DatagramPacket(
                    probe, probe.length,
                    InetAddress.getByName("255.255.255.255"), PORT));
            byte[] buf = new byte[1024];
            DatagramPacket packet = new DatagramPacket(buf, buf.length);
            socket.receive(packet);
            JSONObject json = new JSONObject(new String(packet.getData(), 0, packet.getLength()));
            if (!MAGIC.equals(json.optString("magic"))) {
                return null;
            }
            return new HostInfo(
                    packet.getAddress().getHostAddress(),
                    json.optString("name", "NimbusSeat Host"),
                    json.optInt("api_port", 48120));
        } catch (Exception e) {
            return null;
        }
    }
}
