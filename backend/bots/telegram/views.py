"""Django async view for the Telegram bot webhook."""
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from telegram import Update

from .app_instance import get_bot_app

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
async def telegram_webhook(request):
    """Receive updates from Telegram and dispatch to the bot Application.

    Telegram sends a POST with the Update JSON. We validate the secret token
    header (set via setWebhook) then hand the update to the Application for
    handler dispatch.
    """
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected_secret:
        logger.error("TELEGRAM_WEBHOOK_SECRET not configured; rejecting webhook request")
        return HttpResponseForbidden("Webhook not configured")

    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if received_secret != expected_secret:
        logger.warning("Telegram webhook received invalid secret token")
        return HttpResponseForbidden("Invalid secret token")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    app = await get_bot_app()
    update = Update.de_json(payload, app.bot)
    if update is None:
        return JsonResponse({"error": "could not parse Update"}, status=400)

    try:
        await app.process_update(update)
    except Exception:
        logger.exception("Error processing Telegram update %s", update.update_id)
        # Still return 200 — Telegram will retry otherwise, flooding us with
        # the same bad update.
    return HttpResponse(status=200)
