"""Create an API key for the /v1 service. Run it on your own computer, not in a shared log.

    python scripts/make_api_key.py

Prints the key once (give it to the client privately) and its SHA-256 hash (add the hash
to PHC_API_KEY_HASHES, comma-separated). The service stores and compares hashes only.
"""

import hashlib
import secrets

key = "phc_" + secrets.token_urlsafe(32)
print("key (show once, send privately):", key)
print("hash (for PHC_API_KEY_HASHES):  ", hashlib.sha256(key.encode()).hexdigest())
