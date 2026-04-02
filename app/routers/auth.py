from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import _build_auth_code_flow, _build_msal_app
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", include_in_schema=False)
def login(request: Request):
    flow = _build_auth_code_flow(request, scopes=settings.SCOPE)
    request.session["flow"] = flow
    return templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "auth_url": flow["auth_uri"],
            "app_version": settings.APP_VERSION,
            "company_name": settings.COMPANY_NAME,
        },
    )


@router.get("/authorized", name="authorized", include_in_schema=False)
def authorized(request: Request):
    try:
        flow = request.session.pop("flow", {})
        result = _build_msal_app().acquire_token_by_auth_code_flow(
            flow,
            dict(request.query_params),
        )
        if "error" in result:
            return templates.TemplateResponse(
                "pages/auth_error.html",
                {"request": request, "result": result},
            )
        request.session.clear()
        request.session["user"] = result.get("id_token_claims")
    except ValueError:
        pass  # simply not authenticated yet, redirect to login

    return RedirectResponse(url="/", status_code=302)


@router.get("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    logout_url = (
        f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={request.base_url}"
    )
    return RedirectResponse(url=logout_url)
