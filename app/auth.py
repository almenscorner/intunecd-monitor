import msal
from starlette.requests import Request

from app.config import settings


def _load_cache(request: Request) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    token_cache = request.session.get("token_cache")
    if token_cache:
        cache.deserialize(token_cache)
    return cache


def _save_cache(request: Request, cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        request.session["token_cache"] = cache.serialize()


def _build_msal_app(
    cache: msal.SerializableTokenCache = None,
    authority: str = None,
) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        settings.AZURE_CLIENT_ID,
        authority=authority or settings.AUTHORITY,
        client_credential=settings.AZURE_CLIENT_SECRET,
        token_cache=cache,
    )


def _build_auth_code_flow(request: Request, authority: str = None, scopes: list = None) -> dict:
    return _build_msal_app(authority=authority).initiate_auth_code_flow(
        scopes or [],
        redirect_uri=str(request.url_for("authorized")),
    )


def _get_token_from_cache(request: Request, scope: list = None):
    cache = _load_cache(request)
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(request, cache)
        return result
    return None
