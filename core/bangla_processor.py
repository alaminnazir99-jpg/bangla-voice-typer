"""Bangla text processor.

Handles Bengali Unicode text normalization, punctuation correction,
spacing fixes, and smart punctuation insertion.

Key features:
- যুক্তবর্ণ (conjunct letters) preservation
- Comma (কমা), dāri (দাঁড়ি/।) handling
- Question mark (?) placement
- Spacing normalization
- First-word capitalization for Latin segments
"""

import re


class BanglaProcessor:
    """Process and polish Bangla Unicode text."""

    # Bangla Unicode ranges
    BANGLA_RANGE = r"\u0980-\u09FF"

    # Bangla punctuation
    DARI = "।"  # Bangla danda (full stop)

    # Common question words that end with a question
    QUESTION_WORDS = [
        "কি", "কী", "কেন", "কখন", "কোথায়", "কিভাবে", "কেমন",
        "কে", "কার", "কাদের", "কিসের", "কোন", "কোনটি",
        "কত", "কতটা", "কতজন", "কই", "কারণ", "নাকি",
        "আছে কি", "হবে কি", "পারে কি", "যাবে কি",
    ]

    # Words that typically end with dāri
    END_STOP_WORDS = [
        "থাকবে", "হবে", "গেলাম", "যাই", "আসি", "বলব", "দেবে",
        "করব", "করবে", "পারব", "পারবে", "শেষ", "থামল",
    ]

    # Common filler/noise words to ignore
    FILLER_WORDS = [
        "um", "uh", "ah", "er", "হুম", "আঃ", "উহু", "ইয়ে",
        "একটু", "জানেন", "দেখুন",
    ]

    # Correct common mis-transcriptions
    COMMON_CORRECTIONS = {
        "আমিআমি": "আমি",
        "‌আছে‌": "আছে ",
        "এ": "এ",
        "কি‌ভাবে": "কিভাবে",
        "হ‌য়‌ না": "হয় না",
        "‌": "",
        # Common conjunct/spelling fixes
        "বাংলাদেশ": "বাংলাদেশ",
        "যাইত্তন": "যাচ্ছি",
        "করে‌ছ": "করেছ",
        "করছে‌": "করছে",
        "দ্দারা": "দ্বারা",
        "ভাষা‌টি": "ভাষাটি",
    }

    def __init__(self, auto_punctuation: bool = True, fix_spacing: bool = True):
        self.auto_punctuation = auto_punctuation
        self.fix_spacing = fix_spacing

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(self, raw_text: str) -> str:
        """Process raw recognized text and return polished Bangla."""
        if not raw_text:
            return ""
        text = raw_text
        text = self._clean_text(text)
        text = self._apply_corrections(text)
        text = self._normalize_whitespace(text)
        text = self._fix_spacing(text)
        if self.auto_punctuation:
            text = self._add_punctuation(text)
        text = self._final_cleanup(text)
        return text.strip()

    def apply_corrections(self, text: str) -> str:
        """Apply common corrections without full processing."""
        return self._apply_corrections(text)

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------
    def _clean_text(self, text: str) -> str:
        """Remove unwanted characters while preserving Bangla."""
        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        # Remove excessive spaces
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _apply_corrections(self, text: str) -> str:
        """Apply common corrections for frequent errors."""
        # Join broken characters / fix specific patterns
        replacements = {
            "!": "!",
            "।।": "।",
            "??": "?",
            "?,.": "?",
            "  ": " ",
        }
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)

        # Apply common transcription corrections
        for wrong, correct in self.COMMON_CORRECTIONS.items():
            if wrong and correct and wrong in text:
                text = text.replace(wrong, correct)

        # Fix Bengali question mark usage - often transcribed as dāri
        # Check if sentence ends with Question word + dāri
        for qw in self.QUESTION_WORDS:
            if text.rstrip().endswith(f"{qw}।"):
                text = text.rstrip()[:-1] + "?"
                break

        # Remove filler/interjection words at sentence start where appropriate
        text = re.sub(r"^(হুম|ইয়ে|আঃ|উহু|আচছা|ঠিক আছে)\s*,?\s*", "", text)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize and remove extra whitespace."""
        # Ensure single space between words
        text = re.sub(r"\s+", " ", text)
        # Remove space before punctuation
        text = re.sub(r"\s+([,।?!;:])", r"\1", text)
        # Normalize Bengali comma variations to standard comma
        text = text.replace("،", ",")
        # Ensure space after punctuation (except at sentence end)
        text = re.sub(r"([,;:])(?=[\u0980-\u09FFA-Za-z])", r"\1 ", text)
        return text

    def _is_bangla(self, char: str) -> bool:
        """Check if character is in Bengali Unicode range."""
        return bool(re.match(r"[\u0980-\u09FF]", char))

    def _is_punct(self, char: str) -> bool:
        return char in ",।?!" or char in "?!;:"

    def _fix_spacing(self, text: str) -> str:
        """Fix spacing issues, especially after conjunctions."""
        if not self.fix_spacing:
            return text

        # Fix space before comma, dāri
        text = re.sub(r"\s+([,।?|;:])", r"\1", text)

        # Fix spacing after opening of quotes/brackets in Bangla context
        text = re.sub(r"([\u0980-\u09FF])(['\"_])", r"\1 \2", text)

        # Ensure single space
        text = re.sub(r"\s\s+", " ", text)
        return text

    def _add_punctuation(self, text: str) -> str:
        """Intelligently add punctuation to the text."""
        text = text.strip()

        if not text:
            return text

        # Remove existing trailing punctuation variants
        text = text.rstrip(".,।?!;")

        # Split into sentences at existing dāri/./?
        sentences = re.split(r"(?<=[।?!])", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return ""

        processed = []
        for sentence in sentences:
            rel = self._add_sentence_punctuation(sentence)
            processed.append(rel)

        return " ".join(processed)

    def _add_sentence_punctuation(self, sentence: str) -> str:
        """Add appropriate end punctuation to a single sentence."""
        sentence = sentence.strip()
        if not sentence:
            return ""

        # Determine if it's a question
        is_question = self._is_question(sentence)

        if is_question:
            return sentence + "?"
        else:
            return sentence + "।"

    def _is_question(self, sentence: str) -> bool:
        """Determine if sentence is a question based on content."""
        # Check if ends with question word
        for qw in self.QUESTION_WORDS:
            if sentence.rstrip().endswith(qw):
                return True

        # Check if has question patterns anywhere
        # Ending with what/which/who
        base = sentence.rstrip()
        last_word = base.split()[-1] if base.split() else ""

        # Question particles: কি, না in certain positions
        if " কি " in base or ("কি" in base and "কী" in base):
            return True
        if "কী " in base or base.startswith("কি") or base.startswith("কী"):
            return True

        # Words like "কেন", "কেমন" anywhere at start or middle end
        if any(qw in base and base.rstrip().endswith(last_word)
               for qw in ["কেন", "কেমন", "কবে", "কোনটা"]):
            return True

        return False

    def _final_cleanup(self, text: str) -> str:
        """Final cleanup pass."""
        # Remove leading punctuation
        text = re.sub(r"^[,\.,।\s]+", "", text)
        # Remove double spaces
        text = re.sub(r"\s+", " ", text)
        # Ensure single space after punctuation
        text = re.sub(r"([,।?!;:])(?=[\u0980-\u09FF])", r"\1 ", text)
        return text
