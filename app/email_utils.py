"""
Отправка писем через Gmail SMTP (восстановление пароля и т.п.).

Если GMAIL_ADDRESS/GMAIL_APP_PASSWORD не заданы в переменных окружения —
письма просто не отправляются, а в лог пишется предупреждение. Ничего не
падает: как и с push-уведомлениями (Firebase), отсутствие настроек email
не должно ронять регистрацию/сброс пароля.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def email_is_configured() -> bool:
    return bool(settings.GMAIL_ADDRESS and settings.GMAIL_APP_PASSWORD)


def send_email(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """Отправляет письмо. Возвращает True при успехе, False при любой ошибке
    (недоступность SMTP, неверные креды и т.д.) — не бросает исключений."""
    if not email_is_configured():
        print(f"[EMAIL] GMAIL_ADDRESS/GMAIL_APP_PASSWORD не заданы — письмо '{subject}' для {to_email} не отправлено")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.GMAIL_SENDER_NAME} <{settings.GMAIL_ADDRESS}>"
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_ADDRESS, [to_email], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001 — email не должен ронять запрос
        print(f"[EMAIL] Не удалось отправить '{subject}' на {to_email}: {exc!r}")
        return False


def send_password_reset_code(to_email: str, username: str, code: str) -> bool:
    subject = "Код для восстановления пароля CarSpot"
    text_body = (
        f"Привет, {username}!\n\n"
        f"Твой код для восстановления пароля в CarSpot: {code}\n"
        f"Код действителен {settings.PASSWORD_RESET_CODE_TTL_MINUTES} минут.\n\n"
        "Если ты не запрашивал(а) восстановление пароля — просто проигнорируй это письмо."
    )
    html_body = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a1a;">Восстановление пароля</h2>
      <p>Привет, <b>{username}</b>!</p>
      <p>Твой код для восстановления пароля в CarSpot:</p>
      <p style="font-size: 32px; font-weight: bold; letter-spacing: 6px; background: #f2f2f2;
                padding: 16px 24px; border-radius: 12px; text-align: center; color: #1a1a1a;">
        {code}
      </p>
      <p style="color: #666;">Код действителен {settings.PASSWORD_RESET_CODE_TTL_MINUTES} минут.</p>
      <p style="color: #999; font-size: 13px;">
        Если ты не запрашивал(а) восстановление пароля — просто проигнорируй это письмо.
      </p>
    </div>
    """
    return send_email(to_email, subject, html_body, text_body)
