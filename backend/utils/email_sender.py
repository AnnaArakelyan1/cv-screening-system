import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, body: str):
    if not settings.MAIL_EMAIL or not settings.MAIL_PASSWORD or \
       settings.MAIL_EMAIL == "your_mailtrap_username":
        logger.warning("Email credentials not configured, skipping email send")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.MAIL_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.MAIL_HOST, settings.MAIL_PORT) as server:
            server.starttls()
            server.login(settings.MAIL_EMAIL, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_EMAIL, to_email, msg.as_string())
    except Exception as e:
        logger.warning(f"Failed to send email to {to_email}: {e}")