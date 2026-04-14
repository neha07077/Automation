import os
import sys
import json
import requests
from dotenv import load_dotenv


# Load environment variables
if os.path.exists("config/.env"):
    load_dotenv("config/.env", override=True)
else:
    load_dotenv(override=True)


OS_AUTH_URL = os.getenv("OS_AUTH_URL")
REGION = os.getenv("OS_REGION_NAME", "eu-de-1")
PROJECT_ID = os.getenv("OS_PROJECT_ID")
OS_APPLICATION_CREDENTIAL_ID = os.getenv("OS_APPLICATION_CREDENTIAL_ID")
OS_APPLICATION_CREDENTIAL_SECRET = os.getenv("OS_APPLICATION_CREDENTIAL_SECRET")

required_vars = {
    "OS_AUTH_URL": OS_AUTH_URL,
    "OS_REGION_NAME": REGION,
    "OS_PROJECT_ID": PROJECT_ID,
    "OS_APPLICATION_CREDENTIAL_ID": OS_APPLICATION_CREDENTIAL_ID,
    "OS_APPLICATION_CREDENTIAL_SECRET": OS_APPLICATION_CREDENTIAL_SECRET,
}

for key, value in required_vars.items():
    if not value:
        print(f"Missing required environment variable: {key}")
        sys.exit(1)


COMPUTE_URL = f"https://compute-3.{REGION}.cloud.sap/v2.1/{PROJECT_ID}/servers/detail"
IMAGE_URL = f"https://image-3.{REGION}.cloud.sap/v2/images"

# Approved golden image naming prefixes
APPROVED_PREFIXES = (
    "sap-compliant-",
    "golden-",
    "hardened-",
    "baseline-",
    "cis-",
    "approved-",
)


def get_token() -> str:
    url = f"{OS_AUTH_URL}/auth/tokens"

    payload = {
        "auth": {
            "identity": {
                "methods": ["application_credential"],
                "application_credential": {
                    "id": OS_APPLICATION_CREDENTIAL_ID,
                    "secret": OS_APPLICATION_CREDENTIAL_SECRET
                }
            }
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)

    print("Auth status code:", response.status_code)
    print("Auth response headers:", dict(response.headers))

    if response.status_code not in [200, 201]:
        print("Authentication failed:", response.text)
        sys.exit(1)

    token = (
        response.headers.get("X-Subject-Token")
        or response.headers.get("x-subject-token")
        or response.headers.get("X-Auth-Token")
        or response.headers.get("x-auth-token")
    )

    if not token:
        print("Authentication succeeded but token was not returned.")
        print("Full response body:", response.text)
        sys.exit(1)

    return token


def get_all_images(headers: dict) -> dict:
    image_map = {}
    url = IMAGE_URL

    while url:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            print("Failed to fetch images:", response.text)
            sys.exit(1)

        data = response.json()

        for image in data.get("images", []):
            image_id = image.get("id")
            image_name = image.get("name", "")
            if image_id:
                image_map[image_id] = image_name

        next_link = data.get("next")
        if next_link:
            if next_link.startswith("http"):
                url = next_link
            else:
                url = IMAGE_URL + next_link
        else:
            url = None

    return image_map


def is_golden_image(image_name: str) -> bool:
    if not image_name:
        return False

    image_name = image_name.strip().lower()
    return image_name.startswith(APPROVED_PREFIXES)


def check_compliance():
    print("Generating token...")
    token = get_token()

    headers = {
        "X-Auth-Token": token
    }

    print("Fetching image catalog...")
    image_map = get_all_images(headers)

    print("Fetching servers...")
    response = requests.get(COMPUTE_URL, headers=headers, timeout=30)

    if response.status_code != 200:
        print("Failed to fetch servers:", response.text)
        sys.exit(1)

    servers = response.json().get("servers", [])
    total_servers = len(servers)
    compliant_count = 0
    non_compliant_count = 0
    server_list = []

    print(f"\nTotal servers found: {total_servers}\n")

    for server in servers:
        server_name = server.get("name", "")
        server_id = server.get("id", "")

        image_info = server.get("image") or {}
        image_id = image_info.get("id", "")

        image_name = image_map.get(image_id, "")

        if is_golden_image(image_name):
            status = "COMPLIANT"
            compliant_count += 1
        else:
            status = "NON-COMPLIANT"
            non_compliant_count += 1

        print(f"{server_name} | {server_id} | {image_id} | {image_name} | {status}")

        server_list.append({
            "server_name": server_name,
            "server_id": server_id,
            "image_id": image_id,
            "image_name": image_name,
            "status": status
        })

    output = {
        "summary": {
            "total_servers": total_servers,
            "compliant": compliant_count,
            "non_compliant": non_compliant_count
        },
        "servers": server_list
    }

    with open("golden_image_compliance.json", "w") as f:
        json.dump(output, f, indent=4)

    print("\nJSON saved: golden_image_compliance.json")
    print("\n===== SUMMARY =====")
    print(f"Total Servers : {total_servers}")
    print(f"Compliant     : {compliant_count}")
    print(f"Non-Compliant : {non_compliant_count}")

    if non_compliant_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    check_compliance()
