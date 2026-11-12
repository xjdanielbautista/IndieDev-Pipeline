"""Envío de correos (por ahora solo el de recuperación de contraseña).

EMAIL_PROVIDER elige cómo se envían:
- console (por defecto): no envía nada; escribe el correo en el log del backend.
  Sirve para desarrollo y para probar sin credenciales.
- smtp: servidor SMTP (por ejemplo Gmail con una contraseña de aplicación).
  Variables: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, EMAIL_FROM.
- brevo: API HTTP de Brevo. Variables: BREVO_API_KEY, EMAIL_FROM.
  Útil en hostings que bloquean los puertos SMTP, como el plan gratuito de Render.
"""

import json
import logging
import os
import smtplib
import urllib.request
from email.message import EmailMessage

logger = logging.getLogger("indiedev.mailer")


def _sender() -> str:
    return os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER") or "no-reply@indiedev.local"


def _send_smtp(to: str, subject: str, text: str) -> None:
    message = EmailMessage()
    message["From"] = _sender()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
        server.starttls()
    with server:
        if user and password:
            server.login(user, password)
        server.send_message(message)


def _send_brevo(to: str, subject: str, text: str) -> None:
    body = json.dumps({
        "sender": {"email": _sender(), "name": "IndieDev Pipeline"},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
    }).encode()
    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=body,
        headers={
            "api-key": os.environ["BREVO_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def send_email(to: str, subject: str, text: str) -> None:
    """Envía un correo. Nunca lanza excepciones: los errores solo se registran.

    Se ejecuta en segundo plano después de responder, así que un fallo del
    proveedor no debe tumbar la petición ni revelar si el correo existe.
    """
    provider = os.getenv("EMAIL_PROVIDER", "console").lower()
    try:
        if provider == "smtp":
            _send_smtp(to, subject, text)
        elif provider == "brevo":
            _send_brevo(to, subject, text)
        else:
            logger.warning("EMAIL_PROVIDER=console. Correo para %s: %s\n%s", to, subject, text)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo enviar el correo a %s con el proveedor %s", to, provider)
