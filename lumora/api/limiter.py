from slowapi import Limiter
from slowapi.util import get_remote_address

from lumora.core.config import RATE_LIMIT_PER_MINUTE

limiter = Limiter(key_func=get_remote_address)

RATE_LIMIT = f"{RATE_LIMIT_PER_MINUTE}/minute"
