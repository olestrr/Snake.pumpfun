"""PumpFun livestream chat logger.

This script connects to the PumpFun livestream Socket.IO endpoint and records
incoming chat messages into a newline-delimited JSON (NDJSON) file so the data
can be post-processed later on.

Because the PumpFun websocket schema is subject to change, the script exposes
CLI options to adapt the subscribe payload and the events it listens to without
having to modify the code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import socketio


DEFAULT_SOCKET_URL = "https://pumpportal.fun"
DEFAULT_SUBSCRIBE_EVENT = "subscribe"
DEFAULT_SUBSCRIBE_PAYLOAD = {
    "room": "livestream",
    "channel": "chat",
}
DEFAULT_LISTEN_EVENTS = ("chat_message",)
DEFAULT_HEADERS: Mapping[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Origin": "https://pump.fun",
    "Referer": "https://pump.fun/",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream PumpFun livestream chat messages into a text file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--socket-url",
        default=DEFAULT_SOCKET_URL,
        help="Socket.IO endpoint serving the PumpFun livestream feed.",
    )
    parser.add_argument(
        "--subscribe-event",
        default=DEFAULT_SUBSCRIBE_EVENT,
        help="Socket.IO event name used to subscribe to the livestream room.",
    )
    parser.add_argument(
        "--subscribe-payload",
        default=json.dumps(DEFAULT_SUBSCRIBE_PAYLOAD),
        help=(
            "JSON payload used for the subscription message. "
            "The payload must be compatible with PumpFun's Socket.IO server."
        ),
    )
    parser.add_argument(
        "--listen-event",
        action="append",
        dest="listen_events",
        default=list(DEFAULT_LISTEN_EVENTS),
        help=(
            "Socket.IO event(s) carrying chat messages. "
            "Can be supplied multiple times; each event is persisted."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pumpfun_chat.ndjson"),
        help="Destination file for the chat log (newline-delimited JSON).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the output file instead of truncating it.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Optional maximum run time in seconds; leave empty to run forever.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output for each received message.",
    )
    parser.add_argument(
        "--header",
        action="append",
        dest="headers",
        default=[],
        metavar="KEY:VALUE",
        help=(
            "Additional HTTP headers for the Socket.IO handshake. "
            "Repeat the flag to append multiple headers."
        ),
    )
    parser.add_argument(
        "--no-default-headers",
        action="store_true",
        help="Do not send the built-in browser-style headers when connecting.",
    )
    return parser.parse_args()


class PumpFunChatLogger:
    def __init__(
        self,
        socket_url: str,
        subscribe_event: str,
        subscribe_payload: Dict[str, Any],
        listen_events: Iterable[str],
        output: Path,
        append: bool = False,
        quiet: bool = False,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._socket_url = socket_url
        self._subscribe_event = subscribe_event
        self._subscribe_payload = subscribe_payload
        self._listen_events = tuple(dict.fromkeys(listen_events))
        self._output_path = output
        self._append = append
        self._quiet = quiet
        self._headers = dict(headers or {})
        self._sio = socketio.AsyncClient(logger=False, engineio_logger=False)
        self._file_handle = None

        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._sio.event
        async def connect() -> None:  # type: ignore[override]
            if not self._quiet:
                print("Connected to PumpFun websocket; subscribing to chat feed...")
            await self._sio.emit(self._subscribe_event, self._subscribe_payload)

        @self._sio.event
        async def connect_error(data: Any) -> None:  # type: ignore[override]
            print(f"Connection error: {data}")

        @self._sio.event
        async def disconnect() -> None:  # type: ignore[override]
            if not self._quiet:
                print("Disconnected from PumpFun websocket.")

        async def message_handler(event: str, data: Any) -> None:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "data": data,
            }
            self._file_handle.write(json.dumps(payload, ensure_ascii=False))
            self._file_handle.write("\n")
            self._file_handle.flush()
            if not self._quiet:
                print(f"[{payload['timestamp']}] {event}: {data}")

        for event_name in self._listen_events:
            if not event_name:
                continue

            @self._sio.on(event_name)  # type: ignore[misc]
            async def _handler(data: Any, event=event_name) -> None:
                await message_handler(event, data)

    async def run(self, duration: Optional[int] = None) -> None:
        mode = "a" if self._append else "w"
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._output_path.open(mode, encoding="utf-8") as handle:
            self._file_handle = handle
            await self._sio.connect(
                self._socket_url,
                transports=["websocket"],
                headers=self._headers or None,
            )

            try:
                if duration is not None:
                    await asyncio.wait_for(self._sio.wait(), timeout=duration)
                else:
                    await self._sio.wait()
            except asyncio.TimeoutError:
                if not self._quiet:
                    print("Duration reached; closing connection.")
            finally:
                await self._sio.disconnect()


def main() -> None:
    args = parse_args()
    try:
        subscribe_payload = json.loads(args.subscribe_payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for --subscribe-payload: {exc}") from exc

    header_map: Dict[str, str] = {}
    if not args.no_default_headers:
        header_map.update(DEFAULT_HEADERS)

    for header in args.headers:
        if ":" not in header:
            raise SystemExit(
                "Malformed --header value. Expected KEY:VALUE, "
                f"got {header!r}."
            )
        key, value = header.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise SystemExit("Header name cannot be empty.")
        header_map[key] = value

    logger = PumpFunChatLogger(
        socket_url=args.socket_url,
        subscribe_event=args.subscribe_event,
        subscribe_payload=subscribe_payload,
        listen_events=args.listen_events,
        output=args.output,
        append=args.append,
        quiet=args.quiet,
        headers=header_map,
    )

    try:
        asyncio.run(logger.run(duration=args.duration))
    except KeyboardInterrupt:
        if not args.quiet:
            print("Interrupted by user; shutting down...")


if __name__ == "__main__":
    main()
