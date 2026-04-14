# Import cloud connection function
from auth import create_connection

# Import time module (for delays if needed)
import time

# Import traceback (for error debugging)
import traceback


# ==============================
# CONFIGURATION
# ==============================

# Server name prefix → Sever-1, Sever-2...
SERVER_PREFIX = "Sever"

# Image ID to launch server
IMAGE_ID = "783164db-b3a8-4ff9-abb5-08ca2e0d1db6"

# VM size (CPU/RAM)
FLAVOR_ID = "52"

# Network ID for server
NETWORK_ID = "2f9ea194-39bb-41b4-9585-6a0dbb3b77a4"

# SSH keypair name
KEYPAIR_NAME = "cm-key"

# Number of servers to create
SERVER_COUNT = 5


# ==============================
# CONNECT TO CLOUD
# ==============================

# Create authenticated connection
conn = create_connection()


# ==============================
# CREATE SERVERS
# ==============================

# Loop to create servers
for i in range(1, SERVER_COUNT + 1):

    # Generate server name
    server_name = f"{SERVER_PREFIX}-{i}"

    # Create server
    server = conn.compute.create_server(
        name=server_name,
        image_id=IMAGE_ID.strip(),
        flavor_id=FLAVOR_ID.strip(),
        networks=[{"uuid": NETWORK_ID.strip()}],
        key_name=KEYPAIR_NAME.strip()
    )


# ==============================
# DEBUG OUTPUT
# ==============================

# Print Image ID
print(f"IMAGE_ID = '{IMAGE_ID}'")

# Print Image ID length (check spaces)
print(len(IMAGE_ID))
