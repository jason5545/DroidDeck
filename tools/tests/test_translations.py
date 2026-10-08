from collections import Counter
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

RES = Path(__file__).resolve().parents[2] / "app/src/main/res"
PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[a-zA-Z]")


def entries(path):
    """name -> (tag, attributes other than name, texts) for every string, plurals and array."""
    result = {}
    for element in ET.parse(path).getroot():
        attributes = {k: v for k, v in element.attrib.items() if k != "name"}
        if element.tag == "string":
            texts = [element.text or ""]
        elif element.tag == "plurals":
            texts = {item.get("quantity"): item.text or "" for item in element}
        else:
            texts = [item.text or "" for item in element]
        result[element.get("name")] = (element.tag, attributes, texts)
    return result


def placeholders(text):
    return Counter(PLACEHOLDER.findall(text.replace("%%", "")))


class TraditionalChineseTest(unittest.TestCase):
    """values-zh-rTW is a fork patch (PATCHES.md): it must keep up with the English strings."""

    def test_every_entry_translated_with_the_same_placeholders(self):
        english = {name: entry for name, entry in entries(RES / "values/strings.xml").items()
                   if entry[1].get("translatable") != "false"}
        chinese = entries(RES / "values-zh-rTW/strings.xml")
        self.assertEqual(sorted(set(english) - set(chinese)), [], "English entries without a translation")
        self.assertEqual(sorted(set(chinese) - set(english)), [], "translations of entries English no longer has")
        for name, (tag, attributes, texts) in english.items():
            zh_tag, zh_attributes, zh_texts = chinese[name]
            self.assertEqual((zh_tag, zh_attributes), (tag, attributes), name)
            if tag == "plurals":
                # Chinese has only "other"; it carries the placeholders of English "other".
                self.assertEqual(list(zh_texts), ["other"], name)
                texts, zh_texts = [texts["other"]], [zh_texts["other"]]
            self.assertEqual(len(zh_texts), len(texts), name)
            if attributes.get("formatted") == "false":
                continue
            for en, zh in zip(texts, zh_texts):
                self.assertEqual(placeholders(zh), placeholders(en), name)

    def test_offered_in_androids_language_setting(self):
        locales = ET.parse(RES / "xml/locales_config.xml").getroot()
        names = [locale.get("{http://schemas.android.com/apk/res/android}name") for locale in locales]
        self.assertIn("zh-TW", names)


if __name__ == "__main__":
    unittest.main()
