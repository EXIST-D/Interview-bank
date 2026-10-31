"""Conservative lookup keys, never replacements for original wording."""
import re
import unicodedata
from .catalog import normalize_label


def normalize_question_text(text):
    text = unicodedata.normalize("NFKC", text).strip().casefold()
    # Only a leading list marker / explicit speaker marker is formatting.
    text = re.sub(r"^(?:\d+[.)、]\s*|[（(]\d+[)）]\s*)", "", text)
    text = re.sub(r"^(?:面试官|问|q)\s*[:：]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Spaces next to Chinese characters are typography; keep 'a b' != 'ab'.
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+|\s+(?=[\u3400-\u9fff])", "", text)
    # Preserve operators, code punctuation, versions, B+ trees and C++/C#.
    return text.rstrip("?？。！!").strip()


CONCEPT_KEY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*){1,3}")


def clean_concept(value):
    """A concept key: 2 to 4 dot-separated lowercase segments such as rag.chunking.strategy; None when it does not fit.

    The key names the one knowledge point a question asks about. Questions about the same point share a key whatever
    their wording, so retrieval can offer them to each other when they share almost no characters."""
    if not isinstance(value, str):
        return None
    key = unicodedata.normalize("NFKC", value).strip().casefold()
    return key if len(key) <= 64 and CONCEPT_KEY.fullmatch(key) else None


def normalize_company_alias(text):
    return unicodedata.normalize("NFKC", text).strip().casefold()


def normalize_technology(text):
    return normalize_label("technologies", text)


def legacy_technology_key(text):
    """V1.0 canonical tags remain valid when the alias catalog grows."""
    token = normalize_company_alias(text)
    return {"nodejs": "node.js", "nextjs": "next.js", "postgres": "postgresql",
            "k8s": "kubernetes", "js": "javascript", "ts": "typescript"}.get(token, token)
