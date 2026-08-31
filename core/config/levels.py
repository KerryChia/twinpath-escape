from core.localization import t

LEVELS: dict[str, dict] = {
    "tutorial_001": {
        "map": "assets/tiled/tutorial_001.tmx",
        "zone_subtitle": t("level.tutorial.subtitle"),
        "zone_title": t("level.tutorial.title"),
        "signs": {0: t("level.tutorial.sign.0")},
        "npcs": {"Lizard": {0: t("level.tutorial.npc.lizard.0")}},
        "next_level": "level_001",
        "zoom": None,
        "tutorial": [
            {"keys": ["A", "D"], "text": t("tutorial.move"), "action": "move"},
            {"keys": ["W"], "text": t("tutorial.jump"), "action": "jump"},
            {"keys": ["W", "W"], "text": t("tutorial.double_jump"), "action": "double_jump"},
            {"keys": ["S"], "text": t("tutorial.fast_fall"), "action": "fast_fall"},
        ],
    },
    "level_001": {
        "map": "assets/tiled/level_001.tmx",
        "zone_subtitle": t("level.one.subtitle"),
        "zone_title": t("level.one.title"),
        "signs": {i: t(f"level.one.sign.{i}") for i in range(4)},
        "npcs": {
            "People": {0: t("level.one.npc.people.0")},
            "Duck": {0: t("level.one.npc.duck.0")},
        },
        "next_level": "level_002",
        "zoom": 5.0,
    },
    "level_002": {
        "map": "assets/tiled/level_002.tmx",
        "zone_subtitle": t("level.two.subtitle"),
        "zone_title": t("level.two.title"),
        "signs": {0: t("level.two.sign.0")},
        "npcs": {
            "People": {0: t("level.two.npc.people.0")},
            "Duck": {0: t("level.two.npc.duck.0")},
            "Lizard": {0: t("level.two.npc.lizard.0")},
        },
        "next_level": None,
        "zoom": 5.0,
    },
}
