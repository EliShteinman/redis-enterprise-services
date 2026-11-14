from typing import Literal

type ErrorKind = Literal["customer_fixable", "known_failure", "needs_investigation"]

UNKNOWN_ERROR_KIND: ErrorKind = "needs_investigation"
