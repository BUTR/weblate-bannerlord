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

from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree
from translate.misc.xml_helpers import parse_xml
from translate.storage import base
from translate.storage.flatxml import FlatXMLFile, FlatXMLUnit

from weblate.formats.ttkit import FlatXMLUnit as WeblateFlatXMLUnit
from weblate.formats.ttkit import TTKitFormat


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

    def serialize(self, out) -> None:
        # stable output: keep <string> elements sorted by id (any comments
        # inside <strings> sort to the top)
        strings = self.root.find(self.namespaced("strings"))
        if strings is not None:
            strings[:] = sorted(strings, key=lambda e: e.get(self.key_name) or "")
        super().serialize(out)

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
