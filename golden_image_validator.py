import os
import sys
import json
import ssl
import urllib.request
import urllib.error

def load_env_file(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

load_env_file(".env")
load_env_file("config/.env")

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

APPROVED_PREFIXES = (
    "sap-compliant-",
    "golden-",
    "hardened-",
    "baseline-",
    "cis-",
    "approved-",
)

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def http_request(url, method="GET", headers=None, payload=None):
    if headers is None:
        headers = {}

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, dict(response.headers), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP Error {e.code}: {body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e}")
        sys.exit(1)

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

    headers = {"Content-Type": "application/json"}

    status, response_headers, body = http_request(
        url=url,
        method="POST",
        headers=headers,
        payload=payload
    )

    if status != 201:
        print("Authentication failed:", body)
        sys.exit(1)

    token = response_headers.get("X-Subject-Token")
    if not token:
        print("Authentication succeeded but token was not returned.")
        sys.exit(1)

    return token

def get_all_images(headers: dict) -> dict:
    image_map = {}
    url = IMAGE_URL

    while url:
        status, _, body = http_request(url=url, method="GET", headers=headers)

        if status != 200:
            print("Failed to fetch images")
            sys.exit(1)

        data = json.loads(body)

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
                url = f"{IMAGE_URL}{next_link}" if next_link.startswith("?") else next_link
        else:
            url = None

    return image_map

def is_approved_golden_image(image_name: str) -> bool:
    if not image_name:
        return False
    image_name = image_name.lower()
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
    status, _, body = http_request(url=COMPUTE_URL, method="GET", headers=headers)

    if status != 200:
        print("Failed to fetch servers")
        sys.exit(1)

    servers = json.loads(body).get("servers", [])

    total_servers = len(servers)
    compliant_count = 0
    non_compliant_count = 0
    server_list = []

    print(f"\nTotal servers found: {total_servers}\n")

    for s in servers:
        server_name = s.get("name")
        server_id = s.get("id")

        image_info = s.get("image", {})
        image_id = image_info.get("id")
        image_name = image_map.get(image_id, "")

        if is_approved_golden_image(image_name):
            status_text = "COMPLIANT"
            compliant_count += 1
        else:
            status_text = "NON-COMPLIANT"
            non_compliant_count += 1

        print(f"{server_name} | {server_id} | {image_id} | {image_name} | {status_text}")

        server_list.append({
            "server_name": server_name,
            "server_id": server_id,
            "image_id": image_id,
            "image_name": image_name,
            "status": status_text
        })

    output = {
        "summary": {
            "total_servers": total_servers,
            "compliant": compliant_count,
            "non_compliant": non_compliant_count
        },
        "servers": server_list
    }

    with open("golden_image_compliance.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print("\nJSON saved: golden_image_compliance.json")
    print("\n===== SUMMARY =====")
    print(f"Total Servers   : {total_servers}")
    print(f"Compliant       : {compliant_count}")
    print(f"Non-Compliant   : {non_compliant_count}")

if __name__ == "__main__":
    check_compliance()
