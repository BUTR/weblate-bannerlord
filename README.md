# weblate-bannerlord

Weblate support for Mount & Blade II: Bannerlord module localization.

## File formats

### `Bannerlord language manifest` (`bannerlord-manifest`) — recommended

The translation unit is the whole language folder, addressed via its
`language_data.xml` manifest — exactly how the game sees it:

- File mask: `.../ModuleData/Languages/*/language_data.xml`
- Monolingual base language file & new base: the `EN/` manifest.
- All `<LanguageFile xml_path="..."/>` entries are loaded; every strings file
  of a language shows up in one translation and is committed together
  (multi-file `get_filenames`). Handles vanilla-style per-language filenames
  (`std_common_strings_xml_por-BR.xml`) since the manifest lists exact paths.
- String ids are globally unique per language in Bannerlord; strings added
  through Weblate go to the first listed file (placement is cosmetic to the
  game). Output files keep `<string>` elements sorted by id.
- "Start new translation" builds the full folder: manifest with `id` +
  `supported_iso`, plus blanked copies of every referenced file with the
  `<tag language>` set.

### `Bannerlord language XML` (`bannerlord-xml`) — single file

Legacy/simple variant: mask points at one strings file per language
(`.../Languages/*/sta_strings.xml`). Use `bannerlord-manifest` unless you
have a reason not to. The `CommitLanguageDataAddon` add-on exists for this
format only (the manifest format commits everything natively).

## Language resolution

Language folders are identified by their manifest's `supported_iso` list
(folder names are meaningless to the game), preferring the component's source
language, else the first ISO code Weblate resolves. Tokens pass through
`ISO_OVERRIDES` (`by` → `be_Latn`: country code, used by Bannerlord data to
mean Belarusian in Latin script). Per-project "Language aliases" always win.
Implemented as a `ready()` monkeypatch of `Component.get_language_alias`
(scoped to these formats) — Weblate has no hook for this; review on major
Weblate upgrades.

## Installation (Weblate Docker)

```sh
docker exec <weblate> uv pip install --python /app/venv/bin/python \
    --target /app/data/python git+https://github.com/BUTR/weblate-bannerlord.git
```

Container environment:

```yaml
WEBLATE_ADD_FORMATS: "weblate_bannerlord.formats.BannerlordXMLFormat,weblate_bannerlord.formats.BannerlordManifestFormat"
WEBLATE_ADD_ADDONS: "weblate_bannerlord.addons.CommitLanguageDataAddon"
```

`/app/data/settings-override.py`:

```python
INSTALLED_APPS.append("weblate_bannerlord")
```

Restart afterwards. For a non-Docker install, add the app to
`INSTALLED_APPS` and the format classes to `WEBLATE_FORMATS`.

## Component wizard auto-detection

The package registers a `translation-finder` backend, so the "Add new
translation component" wizard suggests `Bannerlord language manifest` with
the correct `.../Languages/*/language_data.xml` mask and EN template for any
repository layout — matching is anchored at the `Languages/` folder, so the
SDK-specific prefix does not matter.

## Multi-module repositories

One component per `Languages/` root; install the stock **Component
discovery** add-on on the first component:

- Match: `src/(?P<component>[^/]+)/_Module/ModuleData/Languages/(?P<language>[^/]+)/language_data\.xml`
- File format: `Bannerlord language manifest`
- Component name: `{{ component }}`
- Base file / new base: `src/{{ component }}/_Module/ModuleData/Languages/EN/language_data.xml`

Discovery then creates/updates one component per module automatically.
