"""
Payment Router — Mercado Pago Integration
==========================================
Handles checkout preference creation and webhook notifications.

Endpoints:
  POST /payment/create-preference  → Create MP checkout preference
  POST /payment/webhook            → Receive MP payment notifications
  GET  /payment/success            → Payment success page
  GET  /payment/failure            → Payment failure page
  GET  /payment/pending            → Payment pending page
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_current_user, get_optional_user
from database.queries import UserQueries
from database.db_manager import db_manager
import httpx
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payment"])
templates = Jinja2Templates(directory="templates")

# Mercado Pago credentials (production)
MP_ACCESS_TOKEN = os.getenv(
    "MP_ACCESS_TOKEN",
    "APP_USR-6101608656957617-030722-211db365b799047c660314ab9a168033-77950954"
)
MP_PUBLIC_KEY = os.getenv(
    "MP_PUBLIC_KEY",
    "APP_USR-90203641-41cb-4f3c-ab32-8b032736ce06"
)
MP_API_URL = "https://api.mercadopago.com"


# ══════════════════════════════════════════════════════════════════════════════
# CREATE CHECKOUT PREFERENCE
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/create-preference")
async def create_preference(request: Request, user: dict = Depends(get_current_user)):
    """
    Create a Mercado Pago checkout preference for a subscription plan.
    """
    try:
        body = await request.json()
        plan_name = body.get("plan_name", "")
        promo_code = body.get("promo_code", "")

        # Look up plan
        plans = db_manager.get_active_plans()
        plan = next((p for p in plans if p["name"] == plan_name), None)
        if not plan:
            raise HTTPException(status_code=404, detail="Plano nao encontrado")

        if plan["price"] <= 0:
            raise HTTPException(status_code=400, detail="Plano gratuito nao requer pagamento")

        # Apply promo discount if any
        final_price = plan["price"]
        if promo_code:
            promo = db_manager.validate_promo_code(promo_code)
            if promo:
                discount = promo["discount_pct"] / 100
                final_price = round(plan["price"] * (1 - discount), 2)

        if final_price <= 0:
            # 100% discount — activate plan directly
            logger.info(f"[payment] 100% discount for user {user['id']} (plan: {plan_name})")
            success = UserQueries.update_user_plan(user["id"], plan_name)
            if not success:
                logger.error(f"[payment] Failed to activate plan for user {user['id']}")
                raise HTTPException(status_code=500, detail="Erro ao ativar plano. Tente novamente.")
            return JSONResponse({
                "status": "success",
                "message": "Plano ativado com 100% de desconto!",
                "redirect": "/upgrade?activated=1"
            })

        # Build base URL for callbacks
        host = request.headers.get("host", "localhost:8000")
        scheme = "https" if "scope3" in host or "render" in host else "http"
        base_url = f"{scheme}://{host}"

        # Create Mercado Pago preference
        preference_data = {
            "items": [
                {
                    "title": f"SCOPE3 - Plano {plan_name}",
                    "description": plan.get("description", f"Assinatura mensal plano {plan_name}"),
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": final_price,
                }
            ],
            "payer": {
                "email": user.get("email", ""),
            },
            "back_urls": {
                "success": f"{base_url}/payment/success",
                "failure": f"{base_url}/payment/failure",
                "pending": f"{base_url}/payment/pending",
            },
            "auto_return": "approved",
            "external_reference": f"user_{user['id']}_plan_{plan_name}",
            "notification_url": f"{base_url}/payment/webhook",
            "statement_descriptor": "SCOPE3",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MP_API_URL}/checkout/preferences",
                json=preference_data,
                headers={
                    "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )

        if resp.status_code not in (200, 201):
            logger.error(f"[MP] Error creating preference: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=502, detail="Erro ao criar preferencia de pagamento")

        mp_data = resp.json()
        logger.info(f"[MP] Preference created: {mp_data.get('id')} for user {user['id']}")

        return JSONResponse({
            "status": "success",
            "preference_id": mp_data["id"],
            "init_point": mp_data.get("init_point", ""),
            "sandbox_init_point": mp_data.get("sandbox_init_point", ""),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[payment/create-preference] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK — Payment notification from Mercado Pago
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/webhook")
async def payment_webhook(request: Request):
    """
    Receive payment notifications from Mercado Pago.
    When payment is approved, activate the user's plan.
    """
    try:
        body = await request.json()
        logger.info(f"[MP Webhook] Received: {body}")

        action = body.get("action", "")
        data_id = (body.get("data", {}) or {}).get("id")

        if action == "payment.created" or body.get("type") == "payment":
            if not data_id:
                return JSONResponse({"status": "ok"})

            # Fetch payment details from MP API
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{MP_API_URL}/v1/payments/{data_id}",
                    headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
                    timeout=15.0,
                )

            if resp.status_code != 200:
                logger.error(f"[MP Webhook] Error fetching payment {data_id}: {resp.status_code}")
                return JSONResponse({"status": "error"}, status_code=200)

            payment = resp.json()
            status = payment.get("status", "")
            ext_ref = payment.get("external_reference", "")

            logger.info(f"[MP Webhook] Payment {data_id}: status={status}, ref={ext_ref}")

            if status == "approved" and ext_ref:
                # Parse external_reference: "user_{id}_plan_{name}"
                parts = ext_ref.split("_plan_")
                if len(parts) == 2:
                    user_id_str = parts[0].replace("user_", "")
                    plan_name = parts[1]
                    try:
                        user_id = int(user_id_str)
                        success = UserQueries.update_user_plan(user_id, plan_name)
                        if success:
                            logger.info(f"[MP Webhook] Plan '{plan_name}' activated for user {user_id}")
                        else:
                            logger.error(f"[MP Webhook] Failed to update plan for user {user_id}")
                    except ValueError:
                        logger.error(f"[MP Webhook] Invalid user_id in ref: {ext_ref}")

        return JSONResponse({"status": "ok"})

    except Exception as e:
        logger.error(f"[MP Webhook] Error: {e}", exc_info=True)
        return JSONResponse({"status": "ok"})


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACK PAGES
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/success", response_class=HTMLResponse)
async def payment_success(request: Request, user: dict = Depends(get_optional_user)):
    """Payment approved — check and activate plan."""
    # Try to activate plan from query params
    ext_ref = request.query_params.get("external_reference", "")
    payment_status = request.query_params.get("status", "")
    collection_status = request.query_params.get("collection_status", "")

    activated = False
    plan_name = ""

    if (payment_status == "approved" or collection_status == "approved") and ext_ref:
        parts = ext_ref.split("_plan_")
        if len(parts) == 2:
            user_id_str = parts[0].replace("user_", "")
            plan_name = parts[1]
            try:
                user_id = int(user_id_str)
                activated = UserQueries.update_user_plan(user_id, plan_name)
                if activated:
                    logger.info(f"[Payment Success] Plan '{plan_name}' activated for user {user_id}")
            except ValueError:
                pass

    return templates.TemplateResponse("pages/payment_result.html", {
        "request": request,
        "user": user,
        "result": "success",
        "plan_name": plan_name,
        "activated": activated,
    })


@router.get("/failure", response_class=HTMLResponse)
async def payment_failure(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/payment_result.html", {
        "request": request,
        "user": user,
        "result": "failure",
    })


@router.get("/pending", response_class=HTMLResponse)
async def payment_pending(request: Request, user: dict = Depends(get_optional_user)):
    return templates.TemplateResponse("pages/payment_result.html", {
        "request": request,
        "user": user,
        "result": "pending",
    })
