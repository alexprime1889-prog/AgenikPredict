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
    return f'\n\nIMPORTANT: Respond entirely in {name}. All text output must be in {name}.'
