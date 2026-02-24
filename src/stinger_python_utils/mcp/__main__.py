"""Entry-point for ``python -m stinger_python_utils.mcp``."""

from __future__ import annotations

import argparse
import asyncio
import logging


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stinger-mcp-server",
        description="Stinger MCP Server – expose stinger-ipc services over MCP",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    from .server import StingerMCPServer

    server = StingerMCPServer()

    if args.transport == "stdio":
        asyncio.run(server.run_stdio())
    elif args.transport == "sse":
        asyncio.run(server.run_sse(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
