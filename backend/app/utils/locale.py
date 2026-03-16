"""
Locale utilities for LLM language support.

Maps frontend locale codes to language names and generates
LLM prompt instructions for responding in the user's language.
"""

LOCALE_NAMES = {
    'en': 'English',
    'he': 'Hebrew',
    'ru': 'Russian',
    'es': 'Spanish',
    'de': 'German',
    'fr': 'French',
    'it': 'Italian',
    'pt': 'Portuguese',
    'pl': 'Polish',
    'nl': 'Dutch',
    'tr': 'Turkish',
    'ar': 'Arabic',
}


def get_language_name(locale_code: str) -> str:
    """Get full language name from locale code, defaults to English."""
    return LOCALE_NAMES.get(locale_code, 'English')


def get_llm_language_instruction(locale_code: str) -> str:
    """
    Return a prompt suffix instructing the LLM to respond in the given language.

    Returns empty string for English (the default LLM language),
    so existing behavior is unchanged when no locale is set.
    """
    if not locale_code or locale_code == 'en':
        return ''
    name = get_language_name(locale_code)
    rtl_note = '\n- Text direction: Right-to-Left (RTL).' if locale_code in ('he', 'ar') else ''
    return f"""

═══════════════════════════════════════════════════════════════
[LANGUAGE REQUIREMENT — MANDATORY]
═══════════════════════════════════════════════════════════════

You MUST write the ENTIRE response in **{name}** — no exceptions.

- Report title: in {name}
- Report summary: in {name}
- All section titles: in {name}
- All body text: in {name}
- All quoted content: translated to {name}
- All analysis and conclusions: in {name}{rtl_note}

When tools return content in English or mixed languages, you MUST translate it to {name} before including it in the report.
DO NOT mix languages. Every single word of the output must be in {name}.
The only exceptions are: proper nouns (names, brands), technical terms that have no translation, and code/URLs."""
