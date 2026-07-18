"""Small diagnostic CLI. The GUI will use Esp32Client directly in phase 2."""

from __future__ import annotations

import argparse
from .esp32 import Esp32Client


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlador de diagnóstico PianoLED")
    parser.add_argument("--gui", action="store_true", help="Abrir la aplicación gráfica")
    parser.add_argument("--host", default="10.42.0.26", help="IP o nombre mDNS del ESP32")
    parser.add_argument("--port", type=int, default=4210)
    actions = parser.add_subparsers(dest="action")
    actions.add_parser("clear")
    actions.add_parser("ping")
    actions.add_parser("info")
    for name in ("fill", "set"):
        action = actions.add_parser(name)
        if name == "set": action.add_argument("index", type=int)
        action.add_argument("red", type=int)
        action.add_argument("green", type=int)
        action.add_argument("blue", type=int)
    args = parser.parse_args()
    if args.gui:
        from .gui import run
        run()
        return
    if args.action is None:
        parser.error("indica una acción o usa --gui")
    device = Esp32Client(args.host, args.port)
    if args.action == "clear": device.clear()
    elif args.action == "fill": device.fill(args.red, args.green, args.blue)
    elif args.action == "set": device.set_led(args.index, args.red, args.green, args.blue)
    elif args.action == "ping": print("pong" if device.ping() else "sin respuesta")
    else: print(device.info())


if __name__ == "__main__":
    main()
