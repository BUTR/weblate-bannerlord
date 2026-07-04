"""translation-finder backend for Bannerlord language manifests.

Makes the "Add new translation component" wizard suggest the
bannerlord-manifest format for any repository containing
.../Languages/<code>/language_data.xml, regardless of where the module lives
in the tree (the prefix differs between SDKs), instead of the generic
flat-XML per-folder guesses.

Importing this module registers the backend (see apps.CustomizeConfig.ready).
"""

from translation_finder.api import register_discovery
from translation_finder.discovery.base import BaseDiscovery


@register_discovery
class BannerlordManifestDiscovery(BaseDiscovery):
    """Bannerlord ModuleData language manifest discovery."""

    file_format = "bannerlord-manifest"
    origin = "Bannerlord"
    priority = 90
    requires_template = True
    uses_template = True

    def get_masks(self, *, eager: bool = False, hint: str | None = None):
        for path in self.finder.filter_files(r"language_data\.xml"):
            parts = list(path.parts)
            # anchored at .../Languages/<code>/language_data.xml only
            if len(parts) < 3 or parts[-3] != "Languages":
                continue
            yield {"filemask": "/".join([*parts[:-2], "*", "language_data.xml"])}

    def fill_in_template(self, result, source_language=None) -> None:
        # Bannerlord convention names the source folder EN; fall back to the
        # requested source language just in case
        candidates = ["EN", self.source_language.upper(), self.source_language]
        for code in candidates:
            template = result["filemask"].replace("*", code)
            if self.finder.has_file(template):
                result["template"] = template
                return

    def fill_in_new_base(self, result) -> None:
        if "template" in result:
            result["new_base"] = result["template"]
