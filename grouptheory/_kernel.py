"""Bridge to the domain-independent Whetstone kernel (whetstone/).

The concept paper's central claim is that the evidence architecture -- source identity,
append-only event ledger, versioned claims, dispositions, discriminating tells, verified
transfer, metrics -- is domain-independent and shared with the software-engineering
version. This module makes that literal: the group-theory adapter imports and reuses the
SAME kernel modules, it does not re-implement them.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_KERNEL_DIR = os.path.join(os.path.dirname(_HERE), "whetstone")
if _KERNEL_DIR not in sys.path:
    sys.path.insert(0, _KERNEL_DIR)

import events      # noqa: E402  append-only product-event ledger + projections + schema validation
import transfer    # noqa: E402  the two-leg transfer decision table (section 11)
import metrics     # noqa: E402  pilot metrics from the ledger

__all__ = ["events", "transfer", "metrics"]
