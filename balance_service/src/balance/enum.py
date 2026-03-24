from enum import Enum

class TransactionType(str, Enum):
    """Enumeration of valid balance transaction types.

    Attributes:
        CREDIT: Represents an inbound coin transfer (balance increases).
        DEBIT: Represents an outbound coin transfer (balance decreases).
            Reserved for future use; not yet applied by the repository layer.
    """

    CREDIT = "credit"
    DEBIT = "debit"
