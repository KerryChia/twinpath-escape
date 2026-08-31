import unicodedata

import pygame

_CLOSING_PUNCTUATION = set("，。！？；：、）》】」』…,.!?;:)]}")
_OPENING_PUNCTUATION = set("《【「『([{（")


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    word = ""
    for char in text:
        if char == "\n":
            if word:
                tokens.append(word)
                word = ""
            tokens.append(char)
        elif char.isspace():
            if word:
                tokens.append(word)
                word = ""
            tokens.append(" ")
        elif unicodedata.east_asian_width(char) in {"W", "F"}:
            if word:
                tokens.append(word)
                word = ""
            tokens.append(char)
        else:
            word += char
    if word:
        tokens.append(word)
    return tokens


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in _tokens(text):
        if token == "\n":
            lines.append(current.rstrip())
            current = ""
            continue
        candidate = current + token
        if not current or font.size(candidate)[0] <= max_width:
            current = candidate
            continue
        if token in _CLOSING_PUNCTUATION:
            current += token
            continue
        if current.rstrip() and current.rstrip()[-1] in _OPENING_PUNCTUATION:
            opening = current[-1]
            current = current[:-1].rstrip()
            if current:
                lines.append(current)
            current = opening + token.lstrip()
            continue
        lines.append(current.rstrip())
        current = token.lstrip()
        while current and font.size(current)[0] > max_width:
            split = 1
            while split < len(current) and font.size(current[: split + 1])[0] <= max_width:
                split += 1
            lines.append(current[:split])
            current = current[split:]
    if current or not lines:
        lines.append(current.rstrip())
    return lines


def render_multiline(
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    max_width: int,
    line_gap: int = 4,
    align: str = "center",
) -> pygame.Surface:
    lines = wrap_text(text, font, max_width)
    rendered = [font.render(line, True, color) for line in lines]
    width = max((line.get_width() for line in rendered), default=1)
    line_height = font.get_height()
    height = max(1, len(rendered) * line_height + max(0, len(rendered) - 1) * line_gap)
    result = pygame.Surface((width, height), pygame.SRCALPHA)
    y = 0
    for line in rendered:
        x = 0 if align == "left" else (width - line.get_width()) // 2
        result.blit(line, (x, y))
        y += line_height + line_gap
    return result
