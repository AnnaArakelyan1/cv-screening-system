import logging
from config import settings

logger = logging.getLogger(__name__)

DEFAULTS = {
    "groq":      "llama-3.3-70b-versatile",
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

FAST_DEFAULTS = {
    "groq":      "llama-3.1-8b-instant",
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


def generate(prompt: str, fast: bool = False) -> str:
    """Send prompt to the configured LLM provider and return the response text."""
    provider = settings.LLM_PROVIDER.lower()
    model = settings.LLM_MODEL.strip() or (FAST_DEFAULTS[provider] if fast else DEFAULTS.get(provider, ""))

    if provider == "groq":
        return _groq(prompt, model)
    elif provider == "openai":
        return _openai(prompt, model)
    elif provider == "anthropic":
        return _anthropic(prompt, model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose: groq, openai, anthropic")


def _groq(prompt: str, model: str) -> str:
    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _openai(prompt: str, model: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _anthropic(prompt: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
