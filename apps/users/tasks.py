
from django.conf import settings

from backend.celery import app
from backend.mail import (
    send_direct_mail_by_default_bcc,
    send_mail,
    send_mail_from_template,
)


@app.task
def send_email_on_delay(template, context, subject, email):
    """
        send or process email by actual template
    """
    print("delay")
    send_mail_from_template(template, context, subject, email)


@app.task
def send_password_reset_mail(email, token):
    """
        send mail including a link for reset password
    """
    print("reset password")
    url = f"{settings.SITE_URL}/password-reset/?email={email}&token={token}"
    SUBJECT = "Reset Password Request"
    # The HTML body of the email.
    body = """
    <html>
    <head></head>
    <body>
      <h1>
      <p>Please check below link to reset your password.</p>
      <p><a href='{0}'>Click here...</a></p>
    </body>
    </html>
    """.format(url)
    send_mail(SUBJECT, body, email)


@app.task
def send_account_activation_mail(email, username):
    """
        send mail for account activation
    """
    print("account activated")
    SUBJECT = f"Congratulations {username} 🤩"
    # The HTML body of the email.
    body = """
    <html>
    <head></head>
    <body>
      <p>What a lovely day to Lunsjavtale 🤩, We are happy to inform you that your account has been activated successfully 👏 & we Wish you all the best. </p>
      <p>Welcome to Lunsjavtale Family 🙏😇</p>
    </body>
    </html>
    """
    send_direct_mail_by_default_bcc(SUBJECT, body, email)
