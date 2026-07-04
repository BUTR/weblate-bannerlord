# weblate-bannerlord

Weblate support for Mount & Blade II: Bannerlord module localization:

- **`Bannerlord language XML` file format** (`bannerlord-xml`) — reads/writes
  `<string id="..." text="..."/>` entries under `<base>/<strings>`, preserves
  the `<tags>` section, keeps strings sorted by id.
- **Game-layout file naming** — "Start new translation" creates files in the
  game's folder convention (`BR/`, `CNs/`, uppercase two-letter codes), and
  drops a boilerplate `language_data.xml` manifest when none exists.
- **Manifest-driven language resolution** — language folders are identified
  by their `language_data.xml` `supported_iso` list (the folder name itself is
  meaningless to the game), with a pinned map for folders whose manifests are
  ambiguous (`BYc`/`BYl` both declare Belarusian; `BR` lists plain `pt`
  first). Per-project "Language aliases" always win.

Language resolution has no addon/settings hook in Weblate, so the AppConfig's
`ready()` applies a monkeypatch to `Component.get_language_alias`, scoped to
`bannerlord-xml` components. Review it before upgrading Weblate majors.

## Installation (Weblate Docker)

Install into the data volume (no image rebuild):

```sh
pip install --target /app/data/python weblate-bannerlord
# or from git:
pip install --target /app/data/python git+https://github.com/BUTR/weblate-bannerlord.git
```

Then set in the container environment:

```yaml
WEBLATE_ADD_APPS: "weblate_bannerlord"
WEBLATE_ADD_FORMATS: "weblate_bannerlord.formats.BannerlordXMLFormat"
```

and restart. For a non-Docker install, add `weblate_bannerlord` to
`INSTALLED_APPS` and the format class to `WEBLATE_FORMATS` in settings.

## Component recipe

- File mask: `.../ModuleData/Languages/*/<name>.xml` — the `*` must capture
  the language directory; `language_data.xml` is a manifest, not translations.
- Monolingual base language file & new base: the `EN/` file.
- File format: `Bannerlord language XML`.
- Additional commit files: `.../ModuleData/Languages/%(language)s/language_data.xml`
  so generated manifests land in the same commit.
