# gmab/providers/registry.py

import importlib
import pkgutil

from gmab.providers.base import ProviderBase

# Modules in this package that are not providers and must not be auto-imported
# as such. Underscore-prefixed modules (e.g. _template.py) are skipped too.
_NON_PROVIDER_MODULES = {"base", "registry"}


def _discover():
    """Import every provider module in this package so their classes register.

    A ProviderBase subclass only becomes visible once its module is imported;
    importing the package modules here is what makes auto-discovery work. Adding
    a new provider is therefore just dropping a file into gmab/providers/.
    """
    import gmab.providers as package

    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        if module_name.startswith("_") or module_name in _NON_PROVIDER_MODULES:
            continue
        importlib.import_module(f"{package.__name__}.{module_name}")


def _all_subclasses(cls):
    """Yield cls's subclasses recursively (handles future intermediate bases)."""
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def get_registry():
    """Return a {name: provider_class} mapping of all registered providers."""
    _discover()
    return {
        sub.name: sub
        for sub in _all_subclasses(ProviderBase)
        if getattr(sub, "name", None)
    }


def get_available_providers():
    """Return a sorted list of registered provider names."""
    return sorted(get_registry().keys())
