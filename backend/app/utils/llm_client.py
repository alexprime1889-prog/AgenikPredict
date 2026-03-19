"""
LLM client wrapper
Unified OpenAI format calls with tri-model support and automatic fallback
"""

import json
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI

from ..config import Config

logger = logging.getLogger('agenikpredict.llm_client')


class UsageAccumulator:
    """Accumulates token usage across multiple LLM calls."""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def add(self, usage: dict):
        self.prompt_tokens += usage.get('prompt_tokens', 0)
        self.completion_tokens += usage.get('completion_tokens', 0)
        self.calls += 1

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self):
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'llm_calls': self.calls,
        }


class LLMClient:
    """LLM client"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> Tuple[str, Dict[str, int]]:
        """
        Send chat request

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum tokens
            response_format: Response format (e.g. JSON mode)

        Returns:
            Tuple of (model response text, usage dict with prompt_tokens/completion_tokens/total_tokens)
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        # Some models (e.g. MiniMax M2.5) include <think> content that needs to be removed
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        usage = {
            'prompt_tokens': getattr(response.usage, 'prompt_tokens', 0) if response.usage else 0,
            'completion_tokens': getattr(response.usage, 'completion_tokens', 0) if response.usage else 0,
            'total_tokens': getattr(response.usage, 'total_tokens', 0) if response.usage else 0,
        }
        return content, usage
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Send chat request and return JSON

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum tokens

        Returns:
            Tuple of (parsed JSON object, usage dict)
        """
        response, usage = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        try:
            return self._parse_json_text(response), usage
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format from LLM: {response}")

    @classmethod
    def primary(cls):
        """Primary model configured for the application."""
        return cls(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
            model=Config.LLM_MODEL_NAME,
        )

    @classmethod
    def secondary(cls):
        """Cheap model (GLM-5 Turbo) for chat/ontology. Falls back to primary if not configured."""
        if Config.LLM_SECONDARY_API_KEY:
            return cls(
                api_key=Config.LLM_SECONDARY_API_KEY,
                base_url=Config.LLM_SECONDARY_BASE_URL,
                model=Config.LLM_SECONDARY_MODEL_NAME,
            )
        logger.info("Secondary LLM not configured, using primary")
        return cls()

    @classmethod
    def fallback(cls):
        """Fallback model (Gemini 3.1 Pro) for when primary fails."""
        if Config.LLM_FALLBACK_API_KEY:
            return cls(
                api_key=Config.LLM_FALLBACK_API_KEY,
                base_url=Config.LLM_FALLBACK_BASE_URL,
                model=Config.LLM_FALLBACK_MODEL_NAME,
            )
        return None

    @staticmethod
    def _clean_json_text(text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        return cleaned.strip()

    @classmethod
    def _parse_json_text(cls, text: str) -> Dict[str, Any]:
        cleaned = cls._clean_json_text(text)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        start = cleaned.find('{')
        if start == -1:
            raise json.JSONDecodeError("No JSON object found", cleaned, 0)

        depth = 0
        in_string = False
        escape = False

        for idx in range(start, len(cleaned)):
            ch = cleaned[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\\\':
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start:idx + 1])

        raise json.JSONDecodeError("Unterminated JSON object", cleaned, start)

    def _identity(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        return (self.base_url, self.model, self.api_key)

    def _matches(self, api_key: Optional[str], base_url: Optional[str], model: Optional[str]) -> bool:
        return self.api_key == api_key and self.base_url == base_url and self.model == model

    def _candidate_clients(self) -> List["LLMClient"]:
        clients: List["LLMClient"] = []
        seen = {self._identity()}

        def add(client: Optional["LLMClient"]):
            if not client:
                return
            ident = client._identity()
            if ident in seen:
                return
            seen.add(ident)
            clients.append(client)

        # Ontology and chat often start on the cheap secondary model; if that fails,
        # prefer the primary production model before a looser fallback model.
        if self._matches(Config.LLM_SECONDARY_API_KEY, Config.LLM_SECONDARY_BASE_URL, Config.LLM_SECONDARY_MODEL_NAME):
            try:
                add(LLMClient.primary())
            except ValueError:
                logger.info("Primary LLM is not configured, skipping primary fallback candidate")

        try:
            add(LLMClient.fallback())
        except ValueError:
            logger.info("Fallback LLM is not configured, skipping fallback candidate")

        return clients

    def _chat_json_via_text_repair(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        repair_messages = list(messages) + [{
            "role": "user",
            "content": (
                "Return the answer again as a single valid JSON object only. "
                "Do not include markdown fences, explanations, or any text before or after the JSON."
            ),
        }]
        response, usage = self.chat(
            messages=repair_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._parse_json_text(response), usage

    def chat_with_fallback(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """Try primary model, then fallback to Gemini on error."""
        last_error = None
        for idx, client in enumerate([self, *self._candidate_clients()]):
            if idx > 0:
                logger.info(f"Falling back to {client.model}")
            try:
                return client.chat(messages, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed ({client.model}): {e}")
        raise last_error

    def chat_json_with_fallback(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """Try primary model for JSON, then fallback on error."""
        last_error = None
        for idx, client in enumerate([self, *self._candidate_clients()]):
            if idx > 0:
                logger.info(f"Falling back to {client.model}")
            try:
                return client.chat_json(messages, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM JSON call failed ({client.model}): {e}")
                try:
                    return client._chat_json_via_text_repair(messages, **kwargs)
                except Exception as repair_error:
                    last_error = repair_error
                    logger.warning(f"LLM JSON repair failed ({client.model}): {repair_error}")
        raise last_error
