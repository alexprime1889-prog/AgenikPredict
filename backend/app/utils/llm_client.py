"""
LLM client wrapper
Unified OpenAI format calls
"""

import json
import re
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI

from ..config import Config


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
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response), usage
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format from LLM: {cleaned_response}")

