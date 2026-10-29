"""Kinds of attribute values, each knowing its own canonical form.

An attribute's type in the class spec names its kind: "email", "phone", "domain", "url", or a
plain "str". The kind owns exactly one method, `normalize`, and that is the only place its
comparison rules live. The base kind just strips surrounding whitespace; the others refine it.

What is stored is what the user gave (stripped): a phone number reads the way its owner writes
it. Comparison — strong keys, find conditions — goes through `normalize`, so
"+1 (555) 010-2030" and "+15550102030" are one number, and "Ada@Example.com" one address.
"""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

# The public suffix list shipped with tldextract; never fetched over the network.
_SUFFIXES = tldextract.TLDExtract(suffix_list_urls=())


class Value:
    """A plain string. Its canonical form is the string without surrounding whitespace."""

    @staticmethod
    def normalize(raw, **options):
        return raw.strip() if isinstance(raw, str) else raw


class Email(Value):
    @staticmethod
    def normalize(raw, **options):
        if not isinstance(raw, str):
            return raw
        text = raw.strip()
        if text.lower().startswith("mailto:"):
            text = text[len("mailto:"):]
        return text.lower()


class Phone(Value):
    """"+digits" when a country code is written, digits alone otherwise."""

    @staticmethod
    def normalize(raw, **options):
        if not isinstance(raw, str):
            return raw
        text = raw.strip()
        digits = re.sub(r"\D", "", text)
        if text.startswith("00"):
            return "+" + digits[2:]
        return ("+" + digits) if text.startswith("+") else digits


class Domain(Value):
    """A host name: lower case, no scheme, path, port or leading "www.", IDN as punycode."""

    @staticmethod
    def normalize(raw, **options):
        if not isinstance(raw, str):
            return raw
        text = raw.strip().lower()
        host = urlsplit(text if "//" in text else "//" + text).hostname or ""
        host = host.rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        try:
            return host.encode("idna").decode("ascii")
        except UnicodeError:
            return host


# Query parameters that say how someone arrived, not what they asked for.
_TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|yclid|mc_cid|mc_eid|ref|ref_src|igshid)$", re.IGNORECASE)
_DEFAULT_PORTS = {"http": 80, "https": 443}


class Url(Value):
    """A web address, at the level of sameness the comparison needs.

    level="exact" — the same resource: scheme and host in lower case, default port and a
                    trailing slash dropped, query kept as written;
    level="page"  — the same page (default): also without the fragment and tracking
                    parameters, remaining parameters sorted, http and https alike;
    level="site"  — the same site: its registered domain (careers.acme.com -> acme.com,
                    www.bbc.co.uk -> bbc.co.uk).
    """

    @staticmethod
    def normalize(raw, level: str = "page", **options):
        if not isinstance(raw, str):
            return raw
        text = raw.strip()
        if not text:
            return text
        if "//" not in text:
            text = "http://" + text
        parts = urlsplit(text)
        host = Domain.normalize(parts.hostname or "")
        if level == "site":
            extracted = _SUFFIXES(host)
            return extracted.top_domain_under_public_suffix or host
        scheme = parts.scheme.lower()
        try:
            port = parts.port
        except ValueError:
            # `urlsplit` parses lazily and `.port` raises on a port that is not a number. One
            # malformed URL in the record then made every comparison through `canonical()` raise,
            # not only the reads of that value (docs/archive/code-review-2026-09-30.md 3.1.12). A URL
            # nobody can make sense of is kept as it was written; that is what the record is for.
            return text
        netloc = host if port in (None, _DEFAULT_PORTS.get(scheme)) else f"{host}:{port}"
        path = parts.path.rstrip("/")
        if level == "exact":
            return urlunsplit((scheme, netloc, path, parts.query, parts.fragment))
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                                 if not _TRACKING.match(k)))
        return urlunsplit(("https" if scheme in ("http", "https") else scheme, netloc, path, query, ""))


KINDS: dict[str, type[Value]] = {
    "str": Value,
    "email": Email,
    "phone": Phone,
    "domain": Domain,
    "url": Url,
}


def kind_of(spec: dict, attr: str) -> tuple[type[Value], dict] | None:
    """The value kind of an attribute and the options its spec gives it (e.g. a URL level)."""
    declared = next((a for a in spec.get("attributes", []) if a["name"] == attr), None)
    if declared is None:
        return None
    kind = KINDS.get(declared["type"])
    if kind is None:
        return None
    return kind, {k: declared[k] for k in ("level",) if k in declared}


def canonical(spec: dict, attr: str, value):
    """`value` as its attribute's kind compares it; unchanged for attributes of other types."""
    found = kind_of(spec, attr)
    if found is None:
        return value
    kind, options = found
    return kind.normalize(value, **options)


def looks_like(kind: str, raw) -> bool:
    """Whether a value can be what it says it is. Not validation for its own sake: an address
    with no @, a number with no digits, a web address with no host are not written differently —
    they are something else, and the world asks rather than filing them as that kind."""
    if not isinstance(raw, str) or not raw.strip():
        return True
    text = raw.strip()
    if kind == "email":
        return "@" in text and "." in text.split("@")[-1] and " " not in text
    if kind == "phone":
        return sum(c.isdigit() for c in text) >= 5
    if kind in ("url", "domain"):
        host = Domain.normalize(text)
        return bool(host) and "." in host and " " not in host
    return True
