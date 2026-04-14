import os
import sys
import json
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


load_env_file("config/.env")
load_env_file(".env")

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


def http_request(url, method="GET", headers=None, data=None, timeout=30):
    req = urllib.request.Request(url=url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            response_headers = dict(response.getheaders())
            return response.getcode(), response_headers, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, dict(e.headers), body
    except Exception as e:
        print(f"HTTP request failed for {url}: {e}")
        sys.exit(1)


def get_token():
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

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json"
    }

    status_code, response_headers, response_text = http_request(
        url=url,
        method="POST",
        headers=headers,
        data=data
    )

    print("Auth status code:", status_code)
    print("Auth response headers:", response_headers)

    if status_code not in (200, 201):
        print("Authentication failed:", response_text)
        sys.exit(1)

    token = (
        response_headers.get("X-Subject-Token")
        or response_headers.get("x-subject-token")
        or response_headers.get("X-Auth-Token")
        or response_headers.get("x-auth-token")
    )

    if not token:
        print("Authentication succeeded but token was not returned.")
        print("Full response body:", response_text)
        sys.exit(1)

    return token


def get_all_images(headers):
    image_map = {}
    url = IMAGE_URL

    while url:
        status_code, _, response_text = http_request(url=url, method="GET", headers=headers)

        if status_code != 200:
            print("Failed to fetch images:", response_text)
            sys.exit(1)

        data = json.loads(response_text)

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


def is_golden_image(image_name):
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
    status_code, _, response_text = http_request(url=COMPUTE_URL, method="GET", headers=headers)

    if status_code != 200:
        print("Failed to fetch servers:", response_text)
        sys.exit(1)

    response_json = json.loads(response_text)
    servers = response_json.get("servers", [])

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

    with open("golden_image_compliance.json", "w", encoding="utf-8") as f:
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
