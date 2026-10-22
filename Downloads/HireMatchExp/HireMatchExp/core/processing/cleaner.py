
import re
import unicodedata


class TextCleaner:

    LIGATURES = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "•",
        "\u2013": "-",
        "\u2014": "--",
    }

    @classmethod
    def clean(cls, text: str) -> str:
        if not text:
            return ""

        for lig, repl in cls.LIGATURES.items():
            text = text.replace(lig, repl)

        text = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)

        text = unicodedata.normalize("NFKC", text)

        cleaned_chars = []
        for char in text:
            code = ord(char)
            if code in (10, 13, 9):
                cleaned_chars.append(char)
            elif code < 32 or (127 <= code < 160) or unicodedata.category(char) == "Cf":
                continue
            else:
                cleaned_chars.append(char)
        text = "".join(cleaned_chars)

        text = text.replace("\r\n", "\n").replace("\r", "\n")

        text = re.sub(r"([a-zA-Z]{3,})-\n([a-zA-Z]{3,})", r"\1\2", text)

        lines = []
        for line in text.split("\n"):
            stripped_line = re.sub(r"[ \t]+", " ", line).strip()
            lines.append(stripped_line)

        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

        return cleaned_text.strip()
