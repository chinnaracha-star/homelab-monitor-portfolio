import smtplib
from email.message import EmailMessage

from homelab_monitor.notifications.provider import DeliveryError


class EmailProvider:
    channel = "email"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        to_address: str,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        if not host or not from_address or not to_address:
            raise ValueError("SMTP host, from address, and to address are required")
        self.recipient = to_address
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_tls = use_tls
        self._timeout = timeout

    def send(self, message: str) -> None:
        email = EmailMessage()
        email["Subject"] = "HomeLab Monitor notification"
        email["From"] = self._from_address
        email["To"] = self.recipient
        email.set_content(message)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(email)
        except (OSError, smtplib.SMTPException) as error:
            raise DeliveryError(str(error)) from error

    def close(self) -> None:
        return
