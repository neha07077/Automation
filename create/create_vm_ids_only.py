# Import cloud connection function
from auth import create_connection


# ==============================
# CONFIGURATION
# ==============================

# Server name
SERVER_NAME = "cm-server-test"

# Image ID (OS template)
IMAGE_ID = "4e65258c-7fc6-41c6-af17-b6d25894f9ce"

# VM size (CPU/RAM)
FLAVOR_ID = "52"

# Network ID
NETWORK_ID = "2f9ea194-39bb-41b4-9585-6a0dbb3b77a4"

# SSH keypair name
KEYPAIR_NAME = "test key"


# ==============================
# CONNECT TO CLOUD
# ==============================

# Create cloud connection
conn = create_connection()


# ==============================
# CREATE SERVER
# ==============================

# Send create request
server = conn.compute.create_server(
    name=SERVER_NAME,
    image_id=IMAGE_ID,
    flavor_id=FLAVOR_ID,
    networks=[{"uuid": NETWORK_ID}],
    key_name=KEYPAIR_NAME
)

# Confirm request sent
print("CREATE REQUEST SENT")

# Print server ID
print("ID:", server.id)


# ==============================
# WAIT FOR SERVER
# ==============================

# Wait until server becomes ACTIVE or ERROR
server = conn.compute.wait_for_server(server, wait=1200)

# Print current status
print("STATUS:", server.status)


# ==============================
# GET FINAL DETAILS
# ==============================

# Fetch latest server info
server = conn.compute.get_server(server.id)

# Print final status
print("FINAL STATUS:", server.status)

# Print error info if any
print("FAULT:", getattr(server, "fault", None))
