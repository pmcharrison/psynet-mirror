"""Describe JavaScript resources with explicit browser and page lifecycles.

PsyNet separates code that is loaded once for the browser document from code
that is activated for each timeline page. Experiment authors normally attach
these descriptors to :class:`psynet.timeline.Page` or return them from modular
page component hooks.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class JSDependency:
    """An external JavaScript dependency loaded once per browser document.

    Parameters
    ----------
    src
        URL of the JavaScript file.
    """

    src: str

    def __post_init__(self):
        _validate_src(self.src)


@dataclass(frozen=True)
class JSPageScript:
    """A lifecycle-managed JavaScript file activated for each page.

    The file must export an ``activate(context)`` function. The function may
    return a cleanup function, which PsyNet calls before leaving the page.

    Parameters
    ----------
    src
        URL of the JavaScript file.
    """

    src: str

    def __post_init__(self):
        _validate_src(self.src)


def _validate_src(src):
    """Validate a managed JavaScript resource URL."""
    if not isinstance(src, str):
        raise TypeError("JavaScript resource src must be a string.")
    if not src.strip():
        raise ValueError("JavaScript resource src must be non-empty.")


def _normalize_javascript_resources(resources, resource_class, argument_name):
    """Normalize resource strings and descriptors to one descriptor class."""
    if resources is None:
        return []
    if not isinstance(resources, (list, tuple)):
        raise TypeError(f"{argument_name} must be a list or tuple.")

    normalized = []
    for resource in resources:
        if isinstance(resource, resource_class):
            normalized.append(resource)
        elif isinstance(resource, str):
            normalized.append(resource_class(resource))
        else:
            raise TypeError(
                f"{argument_name} entries must be strings or "
                f"{resource_class.__name__} objects."
            )
    return normalized
