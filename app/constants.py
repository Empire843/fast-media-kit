PROVIDERS = {
    "aishop24h": "AIShop24H",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "openai_compatible": "OpenAI-compatible",
}

LANGUAGES = [
    ("Vietnamese", "Vietnamese"),
    ("English", "English"),
    ("Japanese", "Japanese"),
    ("Korean", "Korean"),
    ("Chinese Simplified", "Chinese Simplified"),
    ("Thai", "Thai"),
    ("French", "French"),
    ("Spanish", "Spanish"),
]

DEFAULT_MODELS = {
    "aishop24h": "google/gemini-3-flash-preview",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "openai_compatible": "gpt-4o-mini",
}

DEFAULT_MAX_WORKERS = 7
DEFAULT_MAX_ITEMS = 100
DEFAULT_MAX_CHARS = 30000
