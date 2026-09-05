"""intelligence/providers — provider adapters. anthropic_adapter.py is the only file here (or anywhere in intelligence/) permitted to import the anthropic SDK (spec §6.1, §10).

This package also owns WHICH providers exist. Adding a second provider is a
change inside this package plus its adapter module, and nowhere else: the
gateway asks for a name and gets an adapter or None, and has no list of its own.
"""

SUPPORTED_PROVIDERS = ('anthropic',)


def resolve_adapter(provider_name: str):
    """Return a fresh adapter for `provider_name`, or None if unsupported.

    Deliberately a conditional and not a module-level {name: class} table: a
    table built at import time binds the class by value, which a test-time patch
    of the adapter name could never retroactively affect. This resolves the name
    on every call.
    """
    if provider_name == 'anthropic':
        from .anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    return None
