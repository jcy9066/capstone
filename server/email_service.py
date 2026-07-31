"""SMTP delivery for the project-owned no-reply address."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


class EmailDeliveryError(RuntimeError):
    """Raised without exposing SMTP credentials or provider details to clients."""


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool
    use_ssl: bool
    timeout_sec: int

    @classmethod
    def from_environment(cls) -> "SmtpConfig":
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            timeout = int(os.getenv("SMTP_TIMEOUT_SEC", "10"))
        except ValueError as exc:
            raise EmailDeliveryError("SMTP configuration is invalid.") from exc
        return cls(
            host=os.getenv("SMTP_HOST", "").strip(),
            port=port,
            username=os.getenv("SMTP_USERNAME", "").strip(),
            password=os.getenv("SMTP_PASSWORD", ""),
            from_email=os.getenv("SMTP_FROM_EMAIL", "").strip(),
            from_name=os.getenv("SMTP_FROM_NAME", "Dabom no-reply").strip() or "Dabom no-reply",
            use_tls=_env_bool("SMTP_USE_TLS", True),
            use_ssl=_env_bool("SMTP_USE_SSL", False),
            timeout_sec=max(1, timeout),
        )

    def validate(self) -> None:
        if not all((self.host, self.username, self.password, self.from_email)):
            raise EmailDeliveryError("The no-reply SMTP account is not configured.")
        if self.use_tls and self.use_ssl:
            raise EmailDeliveryError("Choose either SMTP TLS or SMTP SSL, not both.")


class EmailService:
    def __init__(self, config: SmtpConfig | None = None) -> None:
        self.config = config or SmtpConfig.from_environment()

    def send_verification_code(self, recipient: str, code: str, expires_in_minutes: int) -> None:
        self.config.validate()
        message = EmailMessage()
        message["Subject"] = "[Dabom] 회원가입 이메일 인증번호"
        message["From"] = f"{self.config.from_name} <{self.config.from_email}>"
        message["To"] = recipient
        message.set_content(
            "Dabom AI 순찰 로봇 관제 센터 회원가입 인증번호입니다.\n\n"
            f"인증번호: {code}\n"
            f"유효 시간: {expires_in_minutes}분\n\n"
            "본인이 요청하지 않았다면 이 메일을 무시해 주세요. 이 메일에는 회신하지 마세요."
        )
        try:
            if self.config.use_ssl:
                with smtplib.SMTP_SSL(self.config.host, self.config.port, timeout=self.config.timeout_sec) as smtp:
                    smtp.login(self.config.username, self.config.password)
                    smtp.send_message(message)
                return
            with smtplib.SMTP(self.config.host, self.config.port, timeout=self.config.timeout_sec) as smtp:
                smtp.ehlo()
                if self.config.use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(self.config.username, self.config.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("Verification email delivery failed.") from exc
