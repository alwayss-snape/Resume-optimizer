import re

class SafetyGuard:
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"system\s+prompt",
        r"you\s+are\s+now",
        r"reveal\s+secret",
    ]

    def sanitize(self, text: str) -> str:
        """Sanitize text input by escaping system prompt injection attempts."""
        sanitized = text
        for pattern in self.INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[FILTERED_PROMPT_INJECTION_ATTEMPT]", sanitized, flags=re.IGNORECASE)
        return sanitized
