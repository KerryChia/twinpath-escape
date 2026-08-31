import ast
import json
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from core.fonts import FONT_PATH, get_font
from core.localization import placeholders
from core.text import wrap_text

LOCALES = ROOT / "assets" / "locales"


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.font.init()
        cls.en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
        cls.zh = json.loads((LOCALES / "zh_CN.json").read_text(encoding="utf-8"))

    def test_catalog_key_and_placeholder_parity(self) -> None:
        self.assertEqual(self.en.keys(), self.zh.keys())
        for key in self.en:
            self.assertEqual(placeholders(self.en[key]), placeholders(self.zh[key]), key)

    def test_literal_source_locale_keys_exist(self) -> None:
        missing = []
        for path in [*(ROOT / "core").rglob("*.py"), ROOT / "run_game.py"]:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "t"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value not in self.en
                ):
                    missing.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.args[0].value}")
        self.assertEqual(missing, [])

    def test_chinese_catalog_font_coverage(self) -> None:
        self.assertTrue(FONT_PATH.is_file())
        chars = sorted({char for text in self.zh.values() for char in text if "\u3400" <= char <= "\u9fff"})
        missing = [char for char in chars if get_font(20).metrics(char)[0] is None]
        self.assertEqual(missing, [])

    def test_cjk_wrap_width_newlines_and_punctuation(self) -> None:
        font = get_font(20)
        lines = wrap_text("两个人一起前进，传送门才会开启！\n第二行保留。", font, 130)
        self.assertGreater(len(lines), 2)
        self.assertIn("第二行保留。", lines)
        self.assertTrue(all(font.size(line)[0] <= 150 for line in lines))
        self.assertTrue(all(not line.startswith(tuple("，。！？；：、）》】」』")) for line in lines))

    def test_all_font_creation_is_centralized(self) -> None:
        offenders = []
        for path in (ROOT / "core").rglob("*.py"):
            if path.name == "fonts.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in {"Font", "SysFont"}:
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_internal_identifiers_remain_present(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "core").rglob("*.py"))
        for value in [
            '"WASD"', '"Numpad"', '"Arrows"', '"start_game"', '"lobby_update"',
            '"remote_state"', '"tutorial_001"', '"level_001"', '"level_002"',
            '"Floor"', '"Water"', '"BrakablePlatform"', '"MovingPlatforms"',
        ]:
            self.assertIn(value, source)

    def test_tmx_layer_names_are_internal_ascii(self) -> None:
        expected = {"Floor", "Water", "SpawnA", "SpawnB"}
        for path in (ROOT / "assets" / "tiled").glob("*.tmx"):
            names = {element.get("name", "") for element in ET.parse(path).iter() if element.get("name")}
            self.assertTrue(expected.intersection(names), path.name)
            self.assertFalse(any(re.search(r"[\u3400-\u9fff]", name) for name in names), path.name)

    def test_visible_source_literals_are_localized_or_allowlisted(self) -> None:
        allowed = {"", "<", ">"}
        offenders = []
        visible_calls = {"Label", "Button", "TextInput", "FloatingText", "Disconnected", "set_text", "set_caption"}
        for path in (ROOT / "core").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                if name not in visible_calls:
                    continue
                values = list(node.args)
                values.extend(keyword.value for keyword in node.keywords if keyword.arg == "placeholder")
                for value in values:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        text = value.value
                        if text not in allowed and re.search(r"[A-Za-z]{2,}", text):
                            offenders.append(f"{path.relative_to(ROOT)}:{value.lineno}:{text}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
