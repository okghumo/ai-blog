"""
cron_failure_alert.py
======================
Standalone failure alert for the generate_and_email.py cron job.

Deliberately imports NOTHING from `src` — the whole point is to still be able to
tell a human when `src` itself is broken (missing files, bad syntax, whatever
caused the crash this time). Only stdlib + python-dotenv (already a project
dependency), same as setup_cron.py.

Wired in by setup_cron.py's cron line as a shell `||` fallback:
    generate_and_email.py ... || cron_failure_alert.py "$?" ...
so it only runs when the real job exits non-zero, and never adds any overhead
or failure mode to a normal successful run.
"""
import os
import smtplib
import socket
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.resolve()
load_dotenv(PROJECT_ROOT / ".env")

LOG_FILE = PROJECT_ROOT / "data" / "output" / "logs" / "cron_generate_and_email.log"
LOG_TAIL_LINES = 60


def _log_tail() -> str:
    if not LOG_FILE.exists():
        return "(no log file found)"
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-LOG_TAIL_LINES:])


def main() -> None:
    exit_code = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    recipients = [a.strip() for a in os.getenv("ALERT_EMAIL_TO", "").split(",") if a.strip()]

    if not (smtp_host and smtp_user and smtp_pass and recipients):
        print("[cron_failure_alert] SMTP_* / ALERT_EMAIL_TO not configured; cannot send alert.", file=sys.stderr)
        return

    body = (
        f"generate_and_email.py exited with status {exit_code} on {socket.gethostname()} "
        f"at {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC.\n\n"
        f"Last {LOG_TAIL_LINES} lines of {LOG_FILE}:\n\n{_log_tail()}\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = "⚠️ AI Blog Generator: daily cron job FAILED"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())
        print(f"[cron_failure_alert] Sent failure alert to {recipients}")
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[cron_failure_alert] Could not send alert: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
