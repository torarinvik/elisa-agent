"""Constructors of general-purpose values, shared by any domain (THEORY §29.1).

Domains never import each other, so a type two domains both use, such as a
truth value, needs one constructor object they can both name. Only types
whose meaning involves no domain belong here.
"""

from __future__ import annotations

from nca.objects import Constructor

BOOLEAN = Constructor("nca.boolean", "1", 0,
                      "A truth value: a Python bool, or None when the producer has no answer.")
INTEGER = Constructor("nca.integer", "1", 0,
                      "An integer of any size: a Python int, or None when the producer has "
                      "no answer.")

CONSTRUCTORS = (BOOLEAN, INTEGER)
