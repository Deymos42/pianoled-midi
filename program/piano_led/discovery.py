"""Local-network discovery for PianoLED ESP32 controllers."""

from __future__ import annotations

import socket
from dataclasses import dataclass

from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf


@dataclass(frozen=True)
class DiscoveredDevice:
    name: str
    host: str
    port: int


class _Listener(ServiceListener):
    def __init__(self) -> None:
        self.devices: dict[str, DiscoveredDevice] = {}
        self.zeroconf: Zeroconf | None = None

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        self.update_service(zc, service_type, name)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        info = zc.get_service_info(service_type, name)
        if info is None:
            return
        addresses = info.parsed_addresses(IPVersion.V4Only)
        if addresses:
            self.devices[name] = DiscoveredDevice(name.removesuffix("._pianoled._udp.local."), addresses[0], info.port)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        self.devices.pop(name, None)


def discover(timeout: float = 1.5) -> list[DiscoveredDevice]:
    """Return controllers advertised by the ESP32 through mDNS."""
    service_type = "_pianoled._udp.local."
    listener = _Listener()
    with Zeroconf() as zeroconf:
        ServiceBrowser(zeroconf, service_type, listener)
        import time
        time.sleep(timeout)
    return sorted(listener.devices.values(), key=lambda device: device.name)


def resolve_default_host() -> str | None:
    """Fallback for a single device when mDNS browsing is unavailable."""
    try:
        return socket.gethostbyname("pianoled.local")
    except socket.gaierror:
        return None
