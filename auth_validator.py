from __future__ import annotations
import os
import json
import base64
import logging
from dataclasses import dataclass
from typing import Any, Iterable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN}
logger = logging.getLogger("saturday.auth")
@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    roles: tuple[str, ...]
    claims: dict[str, Any]
    @property
    def primary_role(self) -> str:
        return self.roles[0] if self.roles else ROLE_VIEWER
def _normalize_roles(raw_roles: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in raw_roles:
        role = str(value).strip().lower()
        if role in VALID_ROLES and role not in seen:
            seen.append(role)
    if not seen:
        seen.append(ROLE_VIEWER)
    return tuple(seen)
class FirebaseAuthValidator:
    def __init__(
        self,
        service_account_path: str | None = None,
        project_id: str | None = None,
        role_collection: str = "user_roles",
    ) -> None:
        self.security = HTTPBearer(auto_error=False)
        self.role_collection = role_collection
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID")
        self.service_account_path = service_account_path or os.getenv("FIREBASE_SERVICE_ACCOUNT")
        self.strict_prod = os.getenv("SATURDAY_STRICT_PROD", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        requested_mock_auth = os.getenv("SATURDAY_ALLOW_MOCK_AUTH", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.allow_mock_auth = requested_mock_auth and not self.strict_prod
        if requested_mock_auth and self.strict_prod:
            logger.warning("Mock auth requested but blocked because SATURDAY_STRICT_PROD is enabled")
        self._db = None
        self._firebase_enabled = False
        self._try_init_firebase()
    @property
    def firebase_enabled(self) -> bool:
        return self._firebase_enabled
    @property
    def mock_auth_enabled(self) -> bool:
        return self.allow_mock_auth
    def _try_init_firebase(self) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            if not firebase_admin._apps:
                options = {}
                if self.project_id:
                    options["projectId"] = self.project_id
                if self.service_account_path and os.path.exists(self.service_account_path):
                    cred = credentials.Certificate(self.service_account_path)
                    firebase_admin.initialize_app(cred, options=options or None)
                elif self.project_id:
                    firebase_admin.initialize_app(options=options)
            if firebase_admin._apps:
                self._firebase_enabled = True
                try:
                    self._db = firestore.client()
                except Exception as exc:
                    logger.warning("Firestore client unavailable", extra={"error": str(exc)})
                    self._db = None
                logger.info("Firebase auth initialized")
        except Exception as e:
            logger.warning("Firebase init failed", extra={"error": str(e)})
            self._firebase_enabled = False
            self._db = None
    def _extract_roles_from_firestore(self, uid: str) -> tuple[str, ...]:
        if not self._db:
            return (ROLE_VIEWER,)
        try:
            doc = self._db.collection(self.role_collection).document(uid).get()
            if not doc.exists:
                return (ROLE_VIEWER,)
            payload = doc.to_dict() or {}
            if isinstance(payload.get("roles"), list):
                return _normalize_roles(payload["roles"])
            if payload.get("role"):
                return _normalize_roles([str(payload["role"])])
        except Exception:
            pass
        return (ROLE_VIEWER,)
    def _create_mock_user(self, token: str) -> AuthenticatedUser:
        try:
            parts = token.split('.')
            if len(parts) >= 2:
                try:
                    payload = parts[1]
                    padding = 4 - (len(payload) % 4)
                    if padding != 4:
                        payload += '=' * padding
                    payload = payload.replace('-', '+').replace('_', '/')
                    user_data = json.loads(base64.b64decode(payload))
                    roles = _normalize_roles([str(user_data.get("role", ROLE_VIEWER))])
                    return AuthenticatedUser(
                        uid=user_data.get('sub') or user_data.get('uid') or user_data.get('username', 'test_user'),
                        email=f"{user_data.get('username', 'test')}@saturday.local",
                        roles=roles,
                        claims=user_data
                    )
                except Exception:
                    pass
        except Exception:
            pass
        return AuthenticatedUser(
            uid="test_user",
            email="test@saturday.local",
            roles=(ROLE_VIEWER,),
            claims={"role": ROLE_VIEWER}
        )
    def verify_bearer(self, credentials_obj: HTTPAuthorizationCredentials | None) -> AuthenticatedUser:
        if credentials_obj is None or credentials_obj.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token",
            )
        token = credentials_obj.credentials
        if self._firebase_enabled:
            try:
                from firebase_admin import auth as firebase_auth
                claims = firebase_auth.verify_id_token(token, check_revoked=False)
                uid = str(claims["uid"])
                email = claims.get("email")
                roles = self._extract_roles_from_claims(claims)
                if roles == (ROLE_VIEWER,):
                    roles = self._extract_roles_from_firestore(uid)
                return AuthenticatedUser(uid=uid, email=email, roles=roles, claims=claims)
            except Exception as e:
                logger.warning("Firebase token verification failed", extra={"error": str(e)})
                if not self.allow_mock_auth:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid Firebase Bearer token",
                    )
        if not self.allow_mock_auth:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication unavailable: configure Firebase Admin credentials for production.",
            )
        return self._create_mock_user(token)
    def _extract_roles_from_claims(self, claims: dict[str, Any]) -> tuple[str, ...]:
        roles: list[str] = []
        if isinstance(claims.get("roles"), (list, tuple, set)):
            roles.extend(str(r) for r in claims["roles"])
        if claims.get("role") is not None:
            roles.append(str(claims["role"]))
        return _normalize_roles(roles)
    async def authenticated_user(
        self,
        credentials_obj: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    ) -> AuthenticatedUser:
        return self.verify_bearer(credentials_obj)
    def require_roles(self, *required_roles: str):
        normalized_required = set(_normalize_roles(required_roles))
        async def dependency(
            credentials_obj: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
        ) -> AuthenticatedUser:
            user = self.verify_bearer(credentials_obj)
            if not normalized_required.intersection(user.roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required role: {', '.join(sorted(normalized_required))}",
                )
            return user
        return dependency
