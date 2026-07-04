"""Weblate integration for Mount & Blade II: Bannerlord module localization.

The ready() hook patches Component.get_language_alias — Weblate has no addon
or settings hook for language-code resolution, so a targeted monkeypatch
(scoped to bannerlord-xml components) is the only extension point.
"""

import os

from django.apps import AppConfig

# supported_iso tokens that must not resolve as written. "by" is the ISO 3166
# country code for Belarus, not a language code — Weblate's forgiving alias
# table would map it to Belarusian, colliding with the Cyrillic variant; in
# Bannerlord manifests it means Belarusian in Latin script. Folder names are
# never consulted.
ISO_OVERRIDES = {"by": "be_Latn"}


def resolve_from_manifest(component, code):
    """Resolve a language folder via its language_data.xml supported_iso list.

    The game never interprets folder names; the manifest is authoritative:
    <LanguageData id="Português (BR)" supported_iso="pt,por,pt-pt,pt-br" ...>
    Returns the component's source language if listed, else the first ISO
    code Weblate can resolve, else None.
    """
    from lxml import etree

    from weblate.lang.models import Language

    strings_file = os.path.join(component.full_path, component.filemask.replace("*", code))
    manifest = os.path.join(os.path.dirname(strings_file), "language_data.xml")
    if not os.path.isfile(manifest):
        return None
    try:
        root = etree.parse(manifest).getroot()
    except (etree.XMLSyntaxError, OSError):
        return None

    candidates = [
        ISO_OVERRIDES.get(c.strip().lower(), c.strip())
        for c in (root.get("supported_iso") or "").split(",")
        if c.strip()
    ]
    resolved = []
    cache = {}
    for candidate in candidates:
        lang = Language.objects.fuzzy_get_strict(candidate, cache=cache)
        if lang is not None:
            resolved.append(lang.code)
    if not resolved:
        return None
    source = component.source_language.code
    if source in resolved:
        return source
    return resolved[0]


class BannerlordConfig(AppConfig):
    name = "weblate_bannerlord"

    def ready(self) -> None:
        from weblate.trans.models import Component

        orig = Component.get_language_alias

        def get_language_alias(self, code):
            result = orig(self, code)
            if result != code:
                # per-project "Language aliases" field or source mapping won
                return result
            if self.file_format != "bannerlord-xml":
                return code
            return resolve_from_manifest(self, code) or code

        Component.get_language_alias = get_language_alias
