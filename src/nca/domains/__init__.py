"""Task domains: research examples built only from the generic core.

Each subpackage is one domain: its data, its experts, and the experiments
that measure them. Domains depend on the core and never on each other, and
the core never depends on a domain, so a domain can be removed or replaced
without touching the kernel.
"""
