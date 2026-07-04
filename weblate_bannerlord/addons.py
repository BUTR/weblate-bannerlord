"""Weblate add-on: commit generated language_data.xml manifests.

BannerlordXMLFormat.create_new_file writes a language_data.xml manifest next
to a newly created strings file, but Weblate only commits the translation
file itself. This add-on stages the manifest into the same commit, following
the pattern of the stock weblate.gettext.linguas add-on.

Registered via WEBLATE_ADD_ADDONS=weblate_bannerlord.addons.CommitLanguageDataAddon.
"""

import os

from django.utils.translation import gettext_lazy

from weblate.addons.base import BaseAddon
from weblate.addons.events import AddonEvent


class CommitLanguageDataAddon(BaseAddon):
    compat = {"file_format": {"bannerlord-xml"}}
    events = {AddonEvent.EVENT_POST_ADD}
    name = "weblate_bannerlord.language_data"
    verbose = gettext_lazy("Commit Bannerlord language_data.xml")
    description = gettext_lazy(
        "Includes the generated language_data.xml manifest in the commit "
        "when a new language is added."
    )

    def post_add(self, translation, activity_log_id=None):
        component = translation.component
        manifest = os.path.join(
            component.full_path,
            os.path.dirname(translation.filename),
            "language_data.xml",
        )
        with component.repository.lock:
            if os.path.exists(manifest) and component.repository.needs_commit(
                [manifest]
            ):
                translation.addon_commit_files.append(manifest)
