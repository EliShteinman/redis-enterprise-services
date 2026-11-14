from typing import Literal

type ErrorKind = Literal["customer_fixable", "known_failure", "needs_investigation"]

NEEDS_INVESTIGATION: ErrorKind = "needs_investigation"
UNKNOWN_ERROR_KIND: ErrorKind = NEEDS_INVESTIGATION
