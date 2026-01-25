"""
Email service for Loudrr application.

Handles sending transactional emails for:
- Waitlist confirmation (new signups)
- Duplicate registration notices
- Approval notifications (future)

Uses Django's email backend, configurable via settings.
For production, use SMTP services like AWS SES, SendGrid, Mailgun, etc.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_waitlist_confirmation_email(email: str, telegram_url: str) -> bool:
    """
    Send confirmation email for new waitlist signup.

    Args:
        email: User's email address
        telegram_url: Deep link URL to Telegram bot

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Welcome to Loudrr Waitlist!"

    # HTML email content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0a;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" width="100%" max-width="520" cellspacing="0" cellpadding="0" style="max-width: 520px;">
                        <!-- Logo -->
                        <tr>
                            <td align="center" style="padding-bottom: 32px;">
                                <span style="font-size: 28px; font-weight: 700; color: #f95400; letter-spacing: -0.5px;">Loudrr</span>
                            </td>
                        </tr>

                        <!-- Main Content Card -->
                        <tr>
                            <td style="background-color: #141414; border-radius: 16px; padding: 40px 32px; border: 1px solid rgba(255,255,255,0.06);">
                                <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: #ffffff; text-align: center;">
                                    You're on the list!
                                </h1>
                                <p style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.6; color: rgba(255,255,255,0.6); text-align: center;">
                                    Complete your application by connecting your Telegram account. This helps us verify you're a real creator.
                                </p>

                                <!-- CTA Button -->
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td align="center" style="padding: 8px 0 24px 0;">
                                            <a href="{telegram_url}"
                                               style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #ff6b1a 0%, #f95400 50%, #cc4400 100%); color: #000000; font-size: 14px; font-weight: 700; text-decoration: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(249, 84, 0, 0.3);">
                                                Open Telegram
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 0; font-size: 13px; line-height: 1.5; color: rgba(255,255,255,0.4); text-align: center;">
                                    Or copy this link:<br>
                                    <a href="{telegram_url}" style="color: #f95400; text-decoration: none; word-break: break-all;">{telegram_url}</a>
                                </p>
                            </td>
                        </tr>

                        <!-- What's Next -->
                        <tr>
                            <td style="padding: 32px 0;">
                                <h2 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: rgba(255,255,255,0.8); text-align: center;">
                                    What happens next?
                                </h2>
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <table role="presentation" cellspacing="0" cellpadding="0">
                                                <tr>
                                                    <td style="width: 32px; vertical-align: top;">
                                                        <span style="display: inline-block; width: 24px; height: 24px; background-color: rgba(249, 84, 0, 0.15); border-radius: 50%; text-align: center; line-height: 24px; font-size: 12px; color: #f95400; font-weight: 600;">1</span>
                                                    </td>
                                                    <td style="color: rgba(255,255,255,0.5); font-size: 14px; line-height: 1.5;">
                                                        Connect your Telegram account
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <table role="presentation" cellspacing="0" cellpadding="0">
                                                <tr>
                                                    <td style="width: 32px; vertical-align: top;">
                                                        <span style="display: inline-block; width: 24px; height: 24px; background-color: rgba(249, 84, 0, 0.15); border-radius: 50%; text-align: center; line-height: 24px; font-size: 12px; color: #f95400; font-weight: 600;">2</span>
                                                    </td>
                                                    <td style="color: rgba(255,255,255,0.5); font-size: 14px; line-height: 1.5;">
                                                        Link your X (Twitter) account
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0;">
                                            <table role="presentation" cellspacing="0" cellpadding="0">
                                                <tr>
                                                    <td style="width: 32px; vertical-align: top;">
                                                        <span style="display: inline-block; width: 24px; height: 24px; background-color: rgba(249, 84, 0, 0.15); border-radius: 50%; text-align: center; line-height: 24px; font-size: 12px; color: #f95400; font-weight: 600;">3</span>
                                                    </td>
                                                    <td style="color: rgba(255,255,255,0.5); font-size: 14px; line-height: 1.5;">
                                                        Get approved and start earning karma
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.06);">
                                <p style="margin: 0; font-size: 12px; color: rgba(255,255,255,0.3); text-align: center; line-height: 1.6;">
                                    Built to make communities louder, together.<br>
                                    <a href="https://loudrr.com" style="color: rgba(255,255,255,0.4); text-decoration: none;">loudrr.com</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Plain text fallback
    plain_content = f"""
Welcome to Loudrr Waitlist!

You're on the list! Complete your application by connecting your Telegram account.

Open Telegram: {telegram_url}

What happens next?
1. Connect your Telegram account
2. Link your X (Twitter) account
3. Get approved and start earning karma

---
Built to make communities louder, together.
loudrr.com
    """

    try:
        send_mail(
            subject=subject,
            message=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"Waitlist confirmation email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send waitlist confirmation email to {email}: {e}")
        return False


def send_already_registered_email(email: str, telegram_url: str) -> bool:
    """
    Send email for duplicate registration attempts.

    Args:
        email: User's email address
        telegram_url: Deep link URL to continue in Telegram

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Already on the Loudrr Waitlist"

    # HTML email content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0a;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" width="100%" max-width="520" cellspacing="0" cellpadding="0" style="max-width: 520px;">
                        <!-- Logo -->
                        <tr>
                            <td align="center" style="padding-bottom: 32px;">
                                <span style="font-size: 28px; font-weight: 700; color: #f95400; letter-spacing: -0.5px;">Loudrr</span>
                            </td>
                        </tr>

                        <!-- Main Content Card -->
                        <tr>
                            <td style="background-color: #141414; border-radius: 16px; padding: 40px 32px; border: 1px solid rgba(255,255,255,0.06);">
                                <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: #ffffff; text-align: center;">
                                    You're already registered!
                                </h1>
                                <p style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.6; color: rgba(255,255,255,0.6); text-align: center;">
                                    This email is already on the Loudrr waitlist. If you haven't completed your application, click below to continue where you left off.
                                </p>

                                <!-- CTA Button -->
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td align="center" style="padding: 8px 0 24px 0;">
                                            <a href="{telegram_url}"
                                               style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #ff6b1a 0%, #f95400 50%, #cc4400 100%); color: #000000; font-size: 14px; font-weight: 700; text-decoration: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(249, 84, 0, 0.3);">
                                                Continue in Telegram
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 0; font-size: 13px; line-height: 1.5; color: rgba(255,255,255,0.4); text-align: center;">
                                    Or copy this link:<br>
                                    <a href="{telegram_url}" style="color: #f95400; text-decoration: none; word-break: break-all;">{telegram_url}</a>
                                </p>
                            </td>
                        </tr>

                        <!-- Info -->
                        <tr>
                            <td style="padding: 24px 0;">
                                <p style="margin: 0; font-size: 14px; line-height: 1.6; color: rgba(255,255,255,0.4); text-align: center;">
                                    If you didn't request this, you can safely ignore this email.
                                </p>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.06);">
                                <p style="margin: 0; font-size: 12px; color: rgba(255,255,255,0.3); text-align: center; line-height: 1.6;">
                                    Built to make communities louder, together.<br>
                                    <a href="https://loudrr.com" style="color: rgba(255,255,255,0.4); text-decoration: none;">loudrr.com</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Plain text fallback
    plain_content = f"""
You're already registered!

This email is already on the Loudrr waitlist. If you haven't completed your application, click the link below to continue where you left off.

Continue in Telegram: {telegram_url}

If you didn't request this, you can safely ignore this email.

---
Built to make communities louder, together.
loudrr.com
    """

    try:
        send_mail(
            subject=subject,
            message=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"Already registered email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send already registered email to {email}: {e}")
        return False
