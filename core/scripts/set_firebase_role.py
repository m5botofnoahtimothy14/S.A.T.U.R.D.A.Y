import argparse
import os

import firebase_admin
from firebase_admin import auth, credentials


VALID_ROLES = {"viewer", "operator", "admin"}


def init_firebase(service_account_path: str | None, project_id: str | None) -> None:
    if firebase_admin._apps:
        return
    options = {}
    if project_id:
        options["projectId"] = project_id
    if service_account_path:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, options=options or None)
    else:
        firebase_admin.initialize_app(options=options or None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Set Firebase custom role claims for SATURDAY access control")
    parser.add_argument("--uid", required=True)
    parser.add_argument("--role", required=True, choices=sorted(VALID_ROLES))
    parser.add_argument("--service-account", default=os.getenv("FIREBASE_SERVICE_ACCOUNT"))
    parser.add_argument("--project-id", default=os.getenv("FIREBASE_PROJECT_ID"))
    args = parser.parse_args()

    init_firebase(args.service_account, args.project_id)
    auth.set_custom_user_claims(args.uid, {"role": args.role, "roles": [args.role]})
    print(f"Assigned role '{args.role}' to user '{args.uid}'")


if __name__ == "__main__":
    main()
