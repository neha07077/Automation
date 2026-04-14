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

APPROVED_PREFIXES = (
    "sap-compliant-",
    "golden-",
    "hardened-",
    "baseline-",
    "cis-",
    "approved-",
)


def http_json_request(url, method="GET", headers=None, payload=None):
    if headers is None:
        headers = {}

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, dict(e.headers), body
    except Exception as e:
        print(f"Request failed for {url}: {e}")
        sys.exit(1)


def get_token_and_catalog():
    auth_url = f"{OS_AUTH_URL.rstrip('/')}/auth/tokens"

    payload = {
        "auth": {
            "identity": {
                "methods": ["application_credential"],
                "application_credential": {
                    "id": OS_APPLICATION_CREDENTIAL_ID,
                    "secret": OS_APPLICATION_CREDENTIAL_SECRET,
                },
            }
        }
    }

    status, headers, body = http_json_request(
        auth_url,
        method="POST",
        payload=payload,
    )

    print("Generating token...")

    if status != 201:
        print(f"Authentication failed: {status}")
        print(body)
        sys.exit(1)

    token = headers.get("X-Subject-Token") or headers.get("x-subject-token")
    if not token:
        print("Authentication succeeded but token was not returned.")
        sys.exit(1)

    try:
        data = json.loads(body)
        catalog = data["token"]["catalog"]
    except Exception:
        print("Authentication succeeded, but service catalog could not be parsed.")
        sys.exit(1)

    return token, catalog


def get_service_endpoint(catalog, service_type, region, interface="public"):
    for service in catalog:
        if service.get("type") != service_type:
            continue

        for endpoint in service.get("endpoints", []):
            if (
                endpoint.get("interface") == interface
                and endpoint.get("region") == region
            ):
                return endpoint.get("url")

    print(f"Could not find endpoint for service '{service_type}' in region '{region}'.")
    sys.exit(1)


def normalize_endpoint(url):
    return url.rstrip("/")


def get_all_images(headers, image_url):
    print("Fetching image catalog...")

    image_map = {}
    url = f"{normalize_endpoint(image_url)}/images"

    while url:
        status, _, body = http_json_request(url, headers=headers)

        if status != 200:
            print(f"Failed to fetch images: {status}")
            print(body)
            sys.exit(1)

        data = json.loads(body)

        for image in data.get("images", []):
            image_id = image.get("id")
            image_name = image.get("name", "")
            if image_id:
                image_map[image_id] = image_name

        next_link = data.get("next")
        if next_link:
            if next_link.startswith("http://") or next_link.startswith("https://"):
                url = next_link
            else:
                url = f"{normalize_endpoint(image_url)}{next_link}"
        else:
            url = None

    return image_map


def get_all_servers(headers, compute_url):
    print("Fetching servers...")

    status, _, body = http_json_request(
        f"{normalize_endpoint(compute_url)}/servers/detail",
        headers=headers,
    )

    if status != 200:
        print(f"Failed to fetch servers: {status}")
        print(body)
        sys.exit(1)

    data = json.loads(body)
    return data.get("servers", [])


def is_golden_image(image_name):
    if not image_name:
        return False

    image_name = image_name.lower()
    return any(image_name.startswith(prefix) for prefix in APPROVED_PREFIXES)


def check_compliance():
    token, catalog = get_token_and_catalog()

    compute_url = get_service_endpoint(catalog, "compute", REGION)
    image_url = get_service_endpoint(catalog, "image", REGION)

    headers = {
        "X-Auth-Token": token,
        "Accept": "application/json",
    }

    image_map = get_all_images(headers, image_url)
    servers = get_all_servers(headers, compute_url)

    print(f"\nTotal servers found: {len(servers)}\n")

    results = []
    compliant_count = 0
    non_compliant_count = 0

    for server in servers:
        server_name = server.get("name", "UNKNOWN")
        server_id = server.get("id", "UNKNOWN")
        image_info = server.get("image", {}) or {}
        image_id = image_info.get("id", "")
        image_name = image_map.get(image_id, "UNKNOWN_IMAGE")

        compliant = is_golden_image(image_name)
        status = "COMPLIANT" if compliant else "NON-COMPLIANT"

        if compliant:
            compliant_count += 1
        else:
            non_compliant_count += 1

        print(f"{server_name} | {server_id} | {image_id} | {image_name} | {status}")

        results.append(
            {
                "server_name": server_name,
                "server_id": server_id,
                "image_id": image_id,
                "image_name": image_name,
                "status": status,
            }
        )

    with open("golden_image_compliance.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print("\nJSON saved: golden_image_compliance.json")
    print("\n===== SUMMARY =====")
    print(f"Total Servers : {len(servers)}")
    print(f"Compliant     : {compliant_count}")
    print(f"Non-Compliant : {non_compliant_count}")

    if non_compliant_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    check_compliance()
