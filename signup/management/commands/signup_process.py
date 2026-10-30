import time
from logging import getLogger

import djclick
from django.conf import settings

from core.webling_api import WeblingAPI
from signup.services import process_pending

log = getLogger(__name__)


@djclick.command()
@djclick.option("--loop", is_flag=True, help="Run forever, every --interval seconds")
@djclick.option(
    "--interval", type=int, default=120, show_default=True, help="Seconds between two runs"
)
def command(loop: bool, interval: int):
    """Send double opt-in mails for new Webling signups, remind and delete unconfirmed ones."""
    while True:
        try:
            with WeblingAPI(settings.WEBLING_API_KEY) as api:
                stats = process_pending(api)
            djclick.echo(", ".join(f"{name}: {count}" for name, count in stats.items()))
        except Exception:
            if not loop:
                raise
            log.exception("Verarbeitung der Anmeldungen fehlgeschlagen")
        if not loop:
            break
        time.sleep(interval)
