# Import cloud connection function
from auth import create_connection

# Keypair name for SSH access
KEYPAIR_NAME = "cm-key"

# Create cloud connection
conn = create_connection()

# Create SSH keypair
keypair = conn.compute.create_keypair(
    name=KEYPAIR_NAME
)

# Print keypair name
print("Keypair created:", keypair.name)

# Print private key (save it securely)
print("PRIVATE KEY (SAVE THIS):")
print(keypair.private_key)
