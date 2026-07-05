"""Bannerlord ModuleData language XML support for Weblate.

Bannerlord stores translations in attributes, which no stock format reads:

    <base xsi:noNamespaceSchemaLocation=".../ModuleLanguage.xsd">
      <tags>
        <tag language="English" />
      </tags>
      <strings>
        <string id="qZXqV8GzUH" text="Warning from Bannerlord.Harmony!" />
      </strings>
    </base>

Registered via WEBLATE_ADD_FORMATS=weblate_bannerlord.formats.BannerlordXMLFormat
in docker-compose.yml. The <tags> section and any other siblings of <strings>
are preserved untouched on write.
"""

import os
import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree
from translate.misc.xml_helpers import parse_xml
from translate.storage import base
from translate.storage.flatxml import FlatXMLFile, FlatXMLUnit

from weblate.formats.ttkit import FlatXMLUnit as WeblateFlatXMLUnit
from weblate.formats.ttkit import TTKitFormat


_NATURAL_SPLIT = re.compile(r"(\d+)")


def _natural_key(value: str):
    return (
        [
            (0, int(part)) if part.isdigit() else (1, part.casefold())
            for part in _NATURAL_SPLIT.split(value)
        ],
        value,
    )

_XML_DECL_RE = re.compile(rb"^<\?xml[^>]*\?>\s*")
_HEADER_COMMENT_RE = re.compile(rb"<!--[^\0]*?Weblate[^\0]*?-->\s*")

class BannerlordXMLUnit(FlatXMLUnit):
    """A <string id="..." text="..."/> element; value lives in the text attribute."""

    DEFAULT_ELEMENT_NAME = "string"
    DEFAULT_ATTRIBUTE_NAME = "id"

    @property
    def target(self):
        return self.xmlelement.get("text")

    @target.setter
    def target(self, target) -> None:
        self.xmlelement.set("text", target if target is not None else "")


class BannerlordXMLFile(FlatXMLFile):
    """Store for Bannerlord language XML; units live under <base>/<strings>."""

    UnitClass = BannerlordXMLUnit
    _name = "Bannerlord XML File"

    DEFAULT_ROOT_NAME = "base"
    DEFAULT_VALUE_NAME = "string"
    DEFAULT_KEY_NAME = "id"

    @property
    def strings_node(self):
        node = self.root.find(self.namespaced("strings"))
        if node is None:
            node = etree.SubElement(self.root, self.namespaced("strings"))
        return node

    def addunit(self, unit, new=True) -> None:
        unit.namespace = self.namespace
        base.TranslationStore.addunit(self, unit)
        if new:
            self.strings_node.append(unit.xmlelement)

    def removeunit(self, unit) -> None:
        base.TranslationStore.removeunit(self, unit)
        self.strings_node.remove(unit.xmlelement)

    def make_empty_file(self) -> None:
        self.root = etree.Element(self.namespaced(self.root_name))
        etree.SubElement(self.root, self.namespaced("tags"))
        etree.SubElement(self.root, self.namespaced("strings"))
        self.document = self.root.getroottree()

    # id -> rank map derived from the template (EN) unit order; when set it is
    # the primary sort key so translations mirror the dev-controlled EN order
    template_order = None
    # comment placed above the root element of Weblate-written files
    header_comment = None

    def serialize(self, out) -> None:
        # stable output: <string> elements follow the template (EN) order when
        # known; ids absent from the template (and everything when there is no
        # template) fall back to natural sort (digit runs compare numerically:
        # str2 < str10; case-insensitive, raw id as deterministic tiebreaker)
        strings = self.root.find(self.namespaced("strings"))
        if strings is not None:
            # never write empty targets: the game renders text="" as a blank
            # string instead of falling back to English; absent = fallback
            for e in list(strings):
                if e.tag is not etree.Comment and not e.get("text"):
                    strings.remove(e)
            if len(strings) == 0:
                # collapse leftover child indentation so an emptied section
                # serializes as <strings/> instead of a stray blank line
                strings.text = None
            order = self.template_order or {}
            fallback = len(order)
            strings[:] = sorted(
                strings,
                key=lambda e: (
                    order.get(e.get(self.key_name), fallback),
                    _natural_key(e.get(self.key_name) or ""),
                ),
            )
        if not self.header_comment:
            super().serialize(out)
            return
        # lxml cannot reliably emit pre-root comments (setting their tail
        # silently drops them from output), so inject at the byte level after
        # the XML declaration; strip any previous managed comment first
        buf = BytesIO()
        super().serialize(buf)
        data = _HEADER_COMMENT_RE.sub(b"", buf.getvalue(), count=1)
        comment = f"<!--{self.header_comment}-->\n".encode()
        m = _XML_DECL_RE.match(data)
        pos = m.end() if m else 0
        out.write(data[:pos] + comment + data[pos:])

    def parse(self, xml) -> None:
        if not hasattr(self, "filename"):
            self.filename = getattr(xml, "name", "")
        if hasattr(xml, "read"):
            xml.seek(0)
            xml = xml.read()

        self.root = parse_xml(xml, strip_cdata=False)
        self.document = self.root.getroottree()
        self.encoding = self.document.docinfo.encoding or "utf-8"

        root_name = self.namespaced(self.root_name)
        assert self.root.tag == root_name, (
            f"expected root name to be {root_name} but got {self.root.tag}"
        )

        strings = self.root.find(self.namespaced("strings"))
        if strings is not None:
            for entry in strings.iterchildren(self.namespaced(self.value_name)):
                unit = self.UnitClass.createfromxmlElement(
                    entry,
                    namespace=self.namespace,
                    element_name=self.value_name,
                    attribute_name=self.key_name,
                )
                if unit is not None:
                    self.addunit(unit, new=False)


class BannerlordXMLFormat(TTKitFormat):
    name = "Bannerlord language XML"
    format_id = "bannerlord-xml"
    loader = BannerlordXMLFile
    monolingual = True
    unit_class = WeblateFlatXMLUnit
    # used when no "New base file" is set on the component; with a base file
    # Weblate copies it and blanks the text attributes instead
    empty_file_template = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<base xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'\n"
        '      xsi:noNamespaceSchemaLocation="https://raw.githubusercontent.com/BUTR/Bannerlord.XmlSchemas/master/ModuleLanguage.xsd">\n'
        "  <tags>\n"
        '    <tag language="" />\n'
        "  </tags>\n"
        "  <strings>\n"
        "  </strings>\n"
        "</base>\n"
    )

    @classmethod
    def create_new_file(
        cls,
        filename,
        language,
        base,
        callback=None,
        file_format_params=None,
    ) -> None:
        super().create_new_file(filename, language, base, callback, file_format_params)
        # the game only loads languages listed in a language_data.xml manifest;
        # drop a boilerplate one next to the new strings file (add it to the
        # component's "Additional commit files" so it lands in the same commit)
        strings_file = Path(filename)
        lang_name = getattr(language, "name", "") or str(language)
        # the base-file copy keeps the source <tag language>; point it at the
        # new language instead
        try:
            tree = etree.parse(str(strings_file))
            tag = tree.getroot().find("tags/tag")
            if tag is not None:
                tag.set("language", lang_name)
                tree.write(str(strings_file), xml_declaration=True, encoding="utf-8")
        except etree.XMLSyntaxError:
            pass
        manifest = strings_file.parent / "language_data.xml"
        if not manifest.exists():
            name = escape(lang_name, {'"': "&quot;"})
            iso = escape(language.code.replace("_", "-").lower(), {'"': "&quot;"})
            manifest.write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                f'<LanguageData id="{name}" supported_iso="{iso}">\n'
                f'  <LanguageFile xml_path="{strings_file.parent.name}/{strings_file.name}" />\n'
                "</LanguageData>\n",
                encoding="utf-8",
            )


class BannerlordLanguageStore(base.TranslationStore):
    """Multi-file store driven by a language_data.xml manifest.

    The store's file is the manifest; all <LanguageFile xml_path="..."/>
    entries (paths relative to the Languages/ root) are loaded as
    BannerlordXMLFile sub-stores and their units exposed as one store.
    String ids are globally unique per language in Bannerlord, so units are
    keyed by id alone; new units are appended to the first listed file (the
    game merges all files, placement is cosmetic).
    """

    UnitClass = BannerlordXMLUnit
    _name = "Bannerlord Language Store"
    Mimetypes = ["text/xml"]
    Extensions = ["xml"]

    def __init__(self, inputfile=None, **kwargs) -> None:
        self.manifest_tree = None
        self.substores = []  # (absolute path, BannerlordXMLFile)
        super().__init__(**kwargs)
        if inputfile is not None:
            self.parse(inputfile)

    @property
    def file_paths(self):
        return [path for path, _sub in self.substores]

    def parse(self, xml) -> None:
        if not getattr(self, "filename", ""):
            self.filename = getattr(xml, "name", "")
        if hasattr(xml, "read"):
            xml.seek(0)
            xml = xml.read()
        self.manifest_tree = parse_xml(xml, strip_cdata=False).getroottree()
        root = self.manifest_tree.getroot()
        assert root.tag == "LanguageData", (
            f"expected root name to be LanguageData but got {root.tag}"
        )
        if not self.filename:
            # in-memory parse (e.g. upload): sibling files are unreachable
            return
        lang_dir = os.path.dirname(os.path.abspath(self.filename))
        languages_root = os.path.dirname(lang_dir)
        for entry in root.iter("LanguageFile"):
            xml_path = entry.get("xml_path")
            if not xml_path:
                continue
            path = os.path.join(languages_root, *xml_path.split("/"))
            if not os.path.isfile(path):
                continue
            sub = BannerlordXMLFile.parsefile(path)
            self.substores.append((path, sub))
            self.units.extend(sub.units)

    template_order = None
    template_file_index = None
    header_comment = None

    def serialize(self, out) -> None:
        for _path, sub in self.substores:
            sub.template_order = self.template_order
            sub.header_comment = self.header_comment
        # mirror the template's file layout: relocate strings into the file
        # holding the same id in EN (clamped to the files this language has)
        if self.template_file_index and len(self.substores) > 1:
            last = len(self.substores) - 1
            for cur, (_path, sub) in enumerate(self.substores):
                for unit in list(sub.units):
                    want = self.template_file_index.get(unit.source)
                    if want is None or min(want, last) == cur:
                        continue
                    sub.units.remove(unit)
                    elem = unit.xmlelement
                    parent = elem.getparent()
                    if parent is not None:
                        parent.remove(elem)
                    target = self.substores[min(want, last)][1]
                    target.units.append(unit)
                    target.strings_node.append(elem)
        encoding = self.manifest_tree.docinfo.encoding or "utf-8"
        out.write(
            etree.tostring(
                self.manifest_tree, xml_declaration=True, encoding=encoding
            )
        )
        for path, sub in self.substores:
            sub.savefile(path)

    def addunit(self, unit, new=True) -> None:
        if new:
            if not self.substores:
                msg = "manifest lists no existing translation files"
                raise ValueError(msg)
            idx = 0
            if self.template_file_index:
                idx = min(
                    self.template_file_index.get(unit.source, 0),
                    len(self.substores) - 1,
                )
            self.substores[idx][1].addunit(unit)
        self.units.append(unit)

    def removeunit(self, unit) -> None:
        if unit in self.units:
            self.units.remove(unit)
        for _path, sub in self.substores:
            if unit in sub.units:
                sub.removeunit(unit)
                break


class BannerlordManifestFormat(TTKitFormat):
    """Bannerlord language folder addressed via its language_data.xml.

    File mask: .../ModuleData/Languages/*/language_data.xml
    Template & new base: the EN manifest. All strings files referenced by the
    manifest are part of the translation (simple_filename=False makes Weblate
    commit every file reported by get_filenames).
    """

    name = "Bannerlord language manifest"
    format_id = "bannerlord-manifest"
    loader = BannerlordLanguageStore
    monolingual = True
    unit_class = WeblateFlatXMLUnit
    simple_filename = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # translations mirror the dev-controlled EN unit order on save
        template = self.template_store
        if template is None and self.is_template:
            template = self
        if template is not None:
            self.store.template_order = {
                unit.source: idx for idx, unit in enumerate(template.store.units)
            }
            file_map = {}
            for fidx, (_path, sub) in enumerate(
                getattr(template.store, "substores", [])
            ):
                for unit in sub.units:
                    file_map.setdefault(unit.source, fidx)
            self.store.template_file_index = file_map
        if not self.is_template:
            from weblate.utils.site import get_site_url

            self.store.header_comment = (
                " This file is managed by Weblate; do not edit it manually - "
                f"changes would be overwritten. Translate at {get_site_url()} "
            )

    def parse_store(self, storefile):
        # the stock implementation passes bare bytes to the store; the
        # manifest store needs its own path to locate the referenced files
        store = self.get_store_instance()
        if isinstance(storefile, str):
            store.filename = storefile
            content = Path(storefile).read_bytes()
        else:
            store.filename = getattr(storefile, "name", "")
            content = storefile.read()
        store.parse(content)
        return store

    def get_filenames(self):
        paths = super().get_filenames()
        paths.extend(self.store.file_paths)
        return paths

    @classmethod
    def create_new_file(
        cls,
        filename,
        language,
        base,
        callback=None,
        file_format_params=None,
    ) -> None:
        if not base:
            msg = "Bannerlord manifest format requires a new base file"
            raise ValueError(msg)
        lang_name = getattr(language, "name", "") or str(language)
        new_dir = Path(filename).parent
        new_dir.mkdir(parents=True, exist_ok=True)

        base_path = Path(os.path.abspath(base))
        base_root = etree.parse(str(base_path)).getroot()
        languages_root = base_path.parent.parent

        entries = []
        for entry in base_root.iter("LanguageFile"):
            xml_path = entry.get("xml_path")
            if not xml_path:
                continue
            src = languages_root.joinpath(*xml_path.split("/"))
            if not src.is_file():
                continue
            sub = BannerlordXMLFile.parsefile(str(src))
            # keep the template's order in the fresh copy
            sub.template_order = {u.source: i for i, u in enumerate(sub.units)}
            for unit in sub.units:
                unit.target = ""
            tag = sub.root.find("tags/tag")
            if tag is not None:
                tag.set("language", lang_name)
            dest = new_dir / src.name
            sub.savefile(str(dest))
            entries.append(f"{new_dir.name}/{src.name}")

        name = escape(lang_name, {'"': "&quot;"})
        iso = escape(language.code.replace("_", "-").lower(), {'"': "&quot;"})
        lines = "".join(
            f'  <LanguageFile xml_path="{escape(e, {chr(34): "&quot;"})}" />\n'
            for e in entries
        )
        Path(filename).write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<LanguageData id="{name}" supported_iso="{iso}">\n'
            f"{lines}"
            "</LanguageData>\n",
            encoding="utf-8",
        )
