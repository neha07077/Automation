import os
from openstack import connection
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Get required environment variable or raise error
def must_get(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v.strip()

# Create OpenStack connection using application credentials
def create_connection():
    # Print basic config values being used
    print("Using OS_AUTH_URL:", must_get("OS_AUTH_URL"))
    print("Using OS_REGION_NAME:", must_get("OS_REGION_NAME"))
    print("Using OS_INTERFACE:", must_get("OS_INTERFACE"))
    print("Using OS_APPLICATION_CREDENTIAL_ID:", must_get("OS_APPLICATION_CREDENTIAL_ID"))

    # Return authenticated connection object
    return connection.Connection(
        auth_url=must_get("OS_AUTH_URL"),
        region_name=must_get("OS_REGION_NAME"),
        interface=must_get("OS_INTERFACE"),
        identity_api_version=must_get("OS_IDENTITY_API_VERSION"),
        auth_type=must_get("OS_AUTH_TYPE"),
        application_credential_id=must_get("OS_APPLICATION_CREDENTIAL_ID"),
        application_credential_secret=must_get("OS_APPLICATION_CREDENTIAL_SECRET"),
    )
