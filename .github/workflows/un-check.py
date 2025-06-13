#!/usr/bin/env python3

import os
import ssl
import sys
import nntplib
import socket

# Read secrets from environment variables (set in GitHub Secrets)
SERVER = os.getenv("UN_SERVER")
PORT = int(os.getenv("UN_PORT", "563"))
USERNAME = os.getenv("UN_USERNAME")
PASSWORD = os.getenv("UN_PASSWORD")

# Optional group to query (safe way to trigger a usable command)
TEST_GROUP = "alt.binaries.pictures"

def main():
    if not all([SERVER, USERNAME, PASSWORD]):
        print("Missing environment variables!")
        sys.exit(1)

    try:
        context = ssl.create_default_context()
        with nntplib.NNTP_SSL(SERVER, PORT, user=USERNAME, password=PASSWORD, ssl_context=context, timeout=10) as server:
            # Perform a harmless group query to test full login success
            resp, count, first, last, name = server.group(TEST_GROUP)
            print(f"✅ Connected to UNet Server, group {name} has {count} articles")
            sys.exit(0)
    except (nntplib.NNTPError, socket.error, Exception) as e:
        print(f"❌ UNet server check failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()