#!/usr/bin/env python3
"""Run the FamiLator web interface."""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.web import create_app


def main():
    parser = argparse.ArgumentParser(description="FamiLator Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    app = create_app()
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   ███████╗ █████╗ ███╗   ███╗██╗██╗      █████╗     ║
║   ██╔════╝██╔══██╗████╗ ████║██║██║     ██╔══██╗    ║
║   █████╗  ███████║██╔████╔██║██║██║     ███████║    ║
║   ██╔══╝  ██╔══██║██║╚██╔╝██║██║██║     ██╔══██║    ║
║   ██║     ██║  ██║██║ ╚═╝ ██║██║███████╗██║  ██║    ║
║   ╚═╝     ╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚══════╝╚═╝  ╚═╝    ║
║                                                      ║
║   NES/Famicom ROM Translation Toolkit                ║
║                                                      ║
╚══════════════════════════════════════════════════════╝

    Starting web interface at http://{args.host}:{args.port}
    Press Ctrl+C to stop
    """)
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
