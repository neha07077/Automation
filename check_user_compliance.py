import os
import requests
from dotenv import load_dotenv

load_dotenv()

OS_AUTH_URL = os.getenv("OS_AUTH_URL")
OS_PROJECT_ID = os.getenv("OS_PROJECT_ID")

OS_APPLICATION_CREDENTIAL_ID = os.getenv("OS_APPLICATION_CREDENTIAL_ID")
OS_APPLICATION_CREDENTIAL_SECRET = os.getenv("OS_APPLICATION_CREDENTIAL_SECRET")

OS_USERNAME = os.getenv("OS_USERNAME")
OS_PASSWORD = os.getenv("OS_PASSWORD")
OS_USER_DOMAIN_NAME = os.getenv("OS_USER_DOMAIN_NAME", "Default")

if not OS_AUTH_URL or not OS_PROJECT_ID:
    print("Missing required environment variables (OS_AUTH_URL / OS_PROJECT_ID).")
    exit()


def get_token():
    url = f"{OS_AUTH_URL}/auth/tokens"
    headers = {"Content-Type": "application/json"}

    # -----------------------------
    # OPTION 1 — Application Credential
    # -----------------------------
    if OS_APPLICATION_CREDENTIAL_ID and OS_APPLICATION_CREDENTIAL_SECRET:
        print("Authenticating using Application Credential...")

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

    # -----------------------------
    # OPTION 2 — Username/Password
    # -----------------------------
    elif OS_USERNAME and OS_PASSWORD:
        print("Authenticating using Username/Password...")

        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": OS_USERNAME,
                            "domain": {"name": OS_USER_DOMAIN_NAME},
                            "password": OS_PASSWORD
                        }
                    }
                },
                "scope": {
                    "project": {
                        "id": OS_PROJECT_ID
                    }
                }
            }
        }

    else:
        print("No valid authentication method found in .env")
        exit()

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 201:
        print("Authentication Failed:", response.text)
        exit()

    return response.headers["X-Subject-Token"]


def get_role_assignments(token):
    url = f"{OS_AUTH_URL}/role_assignments?scope.project.id={OS_PROJECT_ID}&include_names=True"
    headers = {"X-Auth-Token": token}

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Failed to fetch role assignments:", response.text)
        exit()

    return response.json().get("role_assignments", [])


def is_compliant(username, roles):
    is_technical = username.startswith("T")
    has_admin_substring = any("admin" in r.lower() for r in roles)
    has_exact_admin = any(r.lower() == "admin" for r in roles)

    if is_technical and has_exact_admin:
        return False

    if not is_technical and has_admin_substring and not has_exact_admin:
        return False

    return True


def main():
    print("\nStarting compliance check...\n")

    token = get_token()
    assignments = get_role_assignments(token)

    users_roles = {}

    for assignment in assignments:
        if "user" not in assignment:
            continue

        username = assignment["user"].get("name")
        role_name = assignment["role"].get("name")

        if not username or not role_name:
            continue

        if username not in users_roles:
            users_roles[username] = []

        users_roles[username].append(role_name)

    for username, roles in users_roles.items():
        compliant = is_compliant(username, roles)
        status = "COMPLIANT" if compliant else "NON-COMPLIANT"

        print(f"User: {username}")
        print(f"Roles: {roles}")
        print(f"Status: {status}")
        print("-" * 60)


if __name__ == "__main__":
    main()