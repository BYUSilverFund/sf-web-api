"""Bounded, best-effort credential redaction for opt-in root-span Q&A only.

This is not a general PII scrubber. No prompts, source events or tool payloads
are inspected. Raw content is held only in this request-local bounded buffer.
"""

import json
import os
import re

from openinference.semconv.trace import SpanAttributes as A

MAX_INPUT_CHARS = 4_000
MAX_OUTPUT_CHARS = 16_000
MAX_BUFFER_CHARS = 32_000

_PATTERNS = [
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|$)"
    ),
    re.compile(r"(?i)\b(?:authorization\s*[:=]\s*)?bearer\s+[^\s\"']+"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){0,2}"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{8,}"),
    re.compile(
        r"(?i)[\"']?\b(?:aws[_-]?(?:secret[_-]?access[_-]?key|session[_-]?token)|secret[_-]?access[_-]?key|phoenix[_-]?api[_-]?key|api[_-]?key|access[_-]?token|refresh[_-]?token|password)[\"']?\s*[:=]\s*(?:\"[^\"]*(?:\"|$)|'[^']*(?:'|$)|[^\s,;}]+)"
    ),
]


def _known_secrets():
    return tuple(
        sorted(
            {
                value
                for name, value in os.environ.items()
                if len(value) >= 4
                and (
                    name.endswith(
                        (
                            "API_KEY",
                            "ACCESS_KEY_ID",
                            "SECRET_ACCESS_KEY",
                            "SESSION_TOKEN",
                            "ACCESS_TOKEN",
                            "REFRESH_TOKEN",
                            "PASSWORD",
                            "PRIVATE_KEY",
                        )
                    )
                    or name == "PHOENIX_SECRET"
                )
            },
            key=len,
            reverse=True,
        )
    )


def _redact_and_bound(value, limit, secrets, *, buffer_truncated=False):
    raw = value[:MAX_BUFFER_CHARS]
    clipped = buffer_truncated or len(value) > MAX_BUFFER_CHARS
    for secret in secrets:
        # If the raw buffer ended inside a known long credential, remove the
        # partial value as well; truncation must never make a secret unmatchable.
        if clipped:
            head = secret[:8]
            position = raw.rfind(head)
            if position >= 0 and secret.startswith(raw[position:]):
                raw = raw[:position] + "[REDACTED]"
        raw = raw.replace(secret, "[REDACTED]")
    for pattern in _PATTERNS:
        raw = pattern.sub("[REDACTED]", raw)
    return raw[:limit], clipped or len(raw) > limit, raw != value[:MAX_BUFFER_CHARS]


class RequestContentCapture:
    def __init__(self, span, question):
        self.span = span
        self.secrets = _known_secrets()
        self.answer = ""
        self.buffer_truncated = False
        self.done = False
        self.failed = False
        question, truncated, redacted = _redact_and_bound(
            question, MAX_INPUT_CHARS, self.secrets
        )
        span.set_attribute(A.INPUT_VALUE, question)
        span.set_attribute(A.INPUT_MIME_TYPE, "text/plain")
        span.set_attribute("silverfund.content.input_truncated", truncated)
        span.set_attribute("silverfund.content.redacted", redacted)
        self.redacted = redacted

    def observe(self, frame):
        if frame.startswith("event: done\n"):
            self.done = True
        elif frame.startswith("event: error\n"):
            self.failed = True
        elif frame.startswith("event: delta\n"):
            # Only parse public assistant text; never decode sources/answerContexts.
            delta = json.loads(frame.split("\ndata: ", 1)[1])["text"]
            remaining = MAX_BUFFER_CHARS - len(self.answer)
            self.answer += delta[:remaining]
            self.buffer_truncated |= len(delta) > remaining

    def finish(self, lifecycle):
        if self.failed:
            status = "error"
        elif lifecycle == "exhausted" and self.done:
            status = "completed"
        else:
            status = lifecycle if lifecycle in {"error", "cancelled"} else "incomplete"
        if status == "completed" and not self.answer.strip():
            status = "empty"
        self.span.set_attribute("silverfund.content.status", status)
        # Partial text is deliberately discarded, even if done was yielded just
        # before a transport cancellation. Never show it as a completed answer.
        if status == "completed":
            answer, truncated, redacted = _redact_and_bound(
                self.answer,
                MAX_OUTPUT_CHARS,
                self.secrets,
                buffer_truncated=self.buffer_truncated,
            )
            self.span.set_attribute(A.OUTPUT_VALUE, answer)
            self.span.set_attribute(A.OUTPUT_MIME_TYPE, "text/plain")
            self.span.set_attribute("silverfund.content.output_truncated", truncated)
            self.span.set_attribute(
                "silverfund.content.redacted", self.redacted or redacted
            )
        self.answer = ""
        self.secrets = ()
