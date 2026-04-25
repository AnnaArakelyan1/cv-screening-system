import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings

def send_email(to_email: str, subject: str, body: str):
    if not settings.MAIL_EMAIL or not settings.MAIL_PASSWORD:
        raise Exception("Email credentials not configured")

    msg = MIMEMultipart()
    msg["From"] = settings.MAIL_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain")) 

    with smtplib.SMTP(settings.MAIL_HOST, settings.MAIL_PORT) as server:
        server.starttls()
        server.login(settings.MAIL_EMAIL, settings.MAIL_PASSWORD)
        server.sendmail(settings.MAIL_EMAIL, to_email, msg.as_string())