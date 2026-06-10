"""LAN networking helpers for offline guest sharing."""

import os
import socket


def _ip_from_interface(interface: str) -> str | None:
    import psutil

    try:
        addrs = psutil.net_if_addrs().get(interface, [])
    except Exception:
        return None

    for addr in addrs:
        if addr.family == socket.AF_INET and not addr.address.startswith("127."):
            return addr.address
    return None


def get_local_ip() -> str:
    """Best-effort LAN IP of this machine for guest download URLs."""
    hotspot_ip = os.environ.get("INSTABOOTH_HOTSPOT_IP", "").strip()
    if hotspot_ip:
        return hotspot_ip.split("/")[0]

    hotspot_iface = os.environ.get("INSTABOOTH_HOTSPOT_IFACE", "").strip()
    if hotspot_iface:
        iface_ip = _ip_from_interface(hotspot_iface)
        if iface_ip:
            return iface_ip

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
