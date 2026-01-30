"""
Minimal LLM wrapper with provider-specific handling isolated.

Supports: OpenAI, Anthropic, Google (Gemini), DeepSeek
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import httpx


# =============================================================================
# Shared Data Classes
# =============================================================================

@dataclass
class Function:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str
    function: Function
    extra: Optional[Dict] = None  # Provider-specific data (e.g., Gemini thought_signature)


@dataclass
class Message:
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


@dataclass
class Choice:
    index: int
    message: Message
    finish_reason: Optional[str] = None


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ModelResponse:
    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: Usage = field(default_factory=Usage)


# =============================================================================
# Provider Handlers - Each provider's quirks are isolated here
# =============================================================================

class AnthropicHandler:
    """Handles Anthropic's message format (content blocks, tool_use/tool_result)"""

    endpoint = "https://api.anthropic.com/v1/messages"
    key_env = "ANTHROPIC_API_KEY"

    @staticmethod
    def headers(api_key: str) -> Dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    @staticmethod
    def build_request(
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        tool_choice: Optional[Union[str, Dict]],
        max_tokens: int,
    ) -> Dict:
        system = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        # Convert to Anthropic format
        converted = AnthropicHandler._convert_messages(chat_messages)

        body: Dict[str, Any] = {
            "model": model,
            "messages": converted,
            "max_tokens": max_tokens,
        }

        if system:
            body["system"] = system

        if tools:
            body["tools"] = AnthropicHandler._convert_tools(tools)
            if tool_choice:
                body["tool_choice"] = AnthropicHandler._convert_tool_choice(tool_choice)

        return body

    @staticmethod
    def parse_response(data: Dict) -> ModelResponse:
        content_blocks = data.get("content", [])
        text_content = None
        tool_calls = []

        for block in content_blocks:
            if block["type"] == "text":
                text_content = block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    type="function",
                    function=Function(
                        name=block["name"],
                        arguments=json.dumps(block["input"]),
                    )
                ))

        usage_data = data.get("usage", {})
        return ModelResponse(
            id=data.get("id", ""),
            object="chat.completion",
            created=0,
            model=data.get("model", ""),
            choices=[Choice(
                index=0,
                message=Message(
                    role="assistant",
                    content=text_content,
                    tool_calls=tool_calls if tool_calls else None,
                ),
                finish_reason=data.get("stop_reason"),
            )],
            usage=Usage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            ),
        )

    @staticmethod
    def _convert_messages(messages: List[Dict]) -> List[Dict]:
        """Convert OpenAI-format messages to Anthropic content blocks"""
        result = []

        for msg in messages:
            role = msg.get("role")

            if role == "assistant":
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})

                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        args = tc["function"]["arguments"]
                        if isinstance(args, str):
                            args = json.loads(args)
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args
                        })

                if not content_blocks:
                    content_blocks.append({"type": "text", "text": ""})

                result.append({"role": "assistant", "content": content_blocks})

            elif role == "tool":
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id"),
                    "content": msg.get("content", "")
                }
                # Merge with previous user message if possible
                if result and result[-1]["role"] == "user" and isinstance(result[-1]["content"], list):
                    result[-1]["content"].append(tool_result)
                else:
                    result.append({"role": "user", "content": [tool_result]})

            elif role == "user":
                result.append({"role": "user", "content": msg.get("content", "")})

        return result

    @staticmethod
    def _convert_tools(tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI tool format to Anthropic format"""
        return [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools if t.get("type") == "function"
        ]

    @staticmethod
    def _convert_tool_choice(choice: Union[str, Dict]) -> Dict:
        if choice == "auto":
            return {"type": "auto"}
        elif choice == "required":
            return {"type": "any"}
        elif choice == "none":
            return {"type": "none"}
        elif isinstance(choice, dict):
            return {"type": "tool", "name": choice["function"]["name"]}
        return {"type": "auto"}


class GeminiHandler:
    """Handles Gemini's thought_signature requirement for multi-turn tool calls"""

    endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    key_env = "GEMINI_API_KEY"

    @staticmethod
    def headers(api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def build_request(
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        tool_choice: Optional[Union[str, Dict]],
        max_tokens: int,
    ) -> Dict:
        # Clean and preserve thought_signatures
        cleaned = GeminiHandler._prepare_messages(messages)

        body: Dict[str, Any] = {
            "model": model,
            "messages": cleaned,
            "max_tokens": max_tokens,
        }

        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice

        return body

    @staticmethod
    def parse_response(data: Dict) -> ModelResponse:
        """Parse response and extract thought_signatures from tool calls"""
        choices = []

        for i, choice_data in enumerate(data.get("choices", [])):
            msg_data = choice_data.get("message", {})
            tool_calls = None

            if msg_data.get("tool_calls"):
                tool_calls = []
                for tc in msg_data["tool_calls"]:
                    # Extract thought_signature if present
                    extra = None
                    if "extra_content" in tc:
                        google_extra = tc.get("extra_content", {}).get("google", {})
                        if "thought_signature" in google_extra:
                            extra = {"thought_signature": google_extra["thought_signature"]}

                    tool_calls.append(ToolCall(
                        id=tc["id"],
                        type=tc["type"],
                        function=Function(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        ),
                        extra=extra,
                    ))

            choices.append(Choice(
                index=i,
                message=Message(
                    role=msg_data.get("role", "assistant"),
                    content=msg_data.get("content"),
                    tool_calls=tool_calls,
                ),
                finish_reason=choice_data.get("finish_reason"),
            ))

        usage_data = data.get("usage", {})
        return ModelResponse(
            id=data.get("id", ""),
            object=data.get("object", "chat.completion"),
            created=data.get("created", 0),
            model=data.get("model", ""),
            choices=choices,
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
        )

    @staticmethod
    def _prepare_messages(messages: List[Dict]) -> List[Dict]:
        """Clean messages and preserve thought_signatures for Gemini"""
        cleaned = []

        for msg in messages:
            clean_msg: Dict[str, Any] = {"role": msg["role"]}

            if msg["role"] == "assistant":
                if msg.get("content"):
                    clean_msg["content"] = msg["content"]

                if msg.get("tool_calls"):
                    clean_msg["tool_calls"] = []
                    for tc in msg["tool_calls"]:
                        tool_call: Dict[str, Any] = {
                            "id": tc["id"],
                            "type": tc.get("type", "function"),
                            "function": tc["function"],
                        }
                        # Preserve thought_signature if present
                        if tc.get("extra") and tc["extra"].get("thought_signature"):
                            tool_call["extra_content"] = {
                                "google": {"thought_signature": tc["extra"]["thought_signature"]}
                            }
                        clean_msg["tool_calls"] = clean_msg.get("tool_calls", []) + [tool_call]
                elif not msg.get("content"):
                    clean_msg["content"] = ""

            elif msg["role"] == "tool":
                clean_msg["tool_call_id"] = msg.get("tool_call_id")
                clean_msg["content"] = msg.get("content", "")

            elif msg["role"] in ("user", "system"):
                clean_msg["content"] = msg.get("content", "")

            cleaned.append(clean_msg)

        return cleaned


class OpenAIHandler:
    """Standard OpenAI handler - minimal transformation needed"""

    endpoint = "https://api.openai.com/v1/chat/completions"
    key_env = "OPENAI_API_KEY"

    @staticmethod
    def headers(api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def build_request(
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        tool_choice: Optional[Union[str, Dict]],
        max_tokens: int,
    ) -> Dict:
        # Clean messages (remove None tool_calls, etc.)
        cleaned = OpenAIHandler._clean_messages(messages)

        body: Dict[str, Any] = {
            "model": model,
            "messages": cleaned,
            "max_completion_tokens": max_tokens,
        }

        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice

        return body

    @staticmethod
    def parse_response(data: Dict) -> ModelResponse:
        choices = []

        for i, choice_data in enumerate(data.get("choices", [])):
            msg_data = choice_data.get("message", {})
            tool_calls = None

            if msg_data.get("tool_calls"):
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        type=tc["type"],
                        function=Function(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        )
                    )
                    for tc in msg_data["tool_calls"]
                ]

            choices.append(Choice(
                index=i,
                message=Message(
                    role=msg_data.get("role", "assistant"),
                    content=msg_data.get("content"),
                    tool_calls=tool_calls,
                ),
                finish_reason=choice_data.get("finish_reason"),
            ))

        usage_data = data.get("usage", {})
        return ModelResponse(
            id=data.get("id", ""),
            object=data.get("object", "chat.completion"),
            created=data.get("created", 0),
            model=data.get("model", ""),
            choices=choices,
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
        )

    @staticmethod
    def _clean_messages(messages: List[Dict]) -> List[Dict]:
        """Remove None values and non-standard fields"""
        cleaned = []
        for msg in messages:
            clean_msg: Dict[str, Any] = {"role": msg["role"]}

            if msg["role"] == "assistant":
                if msg.get("content"):
                    clean_msg["content"] = msg["content"]
                if msg.get("tool_calls"):
                    clean_msg["tool_calls"] = msg["tool_calls"]
                elif not msg.get("content"):
                    clean_msg["content"] = ""

            elif msg["role"] == "tool":
                clean_msg["tool_call_id"] = msg.get("tool_call_id")
                clean_msg["content"] = msg.get("content", "")

            elif msg["role"] in ("user", "system"):
                clean_msg["content"] = msg.get("content", "")

            cleaned.append(clean_msg)

        return cleaned


class DeepSeekHandler(OpenAIHandler):
    """DeepSeek uses OpenAI-compatible API"""
    endpoint = "https://api.deepseek.com/chat/completions"
    key_env = "DEEPSEEK_API_KEY"

    @staticmethod
    def build_request(
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        tool_choice: Optional[Union[str, Dict]],
        max_tokens: int,
    ) -> Dict:
        # Same as OpenAI but uses max_tokens instead of max_completion_tokens
        cleaned = OpenAIHandler._clean_messages(messages)

        body: Dict[str, Any] = {
            "model": model,
            "messages": cleaned,
            "max_tokens": max_tokens,
        }

        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice

        return body


# =============================================================================
# Provider Registry
# =============================================================================

PROVIDERS = {
    "openai": OpenAIHandler,
    "anthropic": AnthropicHandler,
    "google": GeminiHandler,
    "deepseek": DeepSeekHandler,
}


# =============================================================================
# Main Entry Point
# =============================================================================

def completion(
    model: str,
    messages: List[Dict[str, Any]],
    provider: str,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None,
    max_tokens: int = 4096,
    timeout: float = 120.0,
) -> ModelResponse:
    """
    Unified completion API for multiple providers.

    Args:
        model: Model identifier (e.g., "gpt-4", "claude-sonnet-4-5", "gemini-2.5-pro")
        messages: List of message dicts with 'role' and 'content'
        provider: Provider name ("openai", "anthropic", "google", "deepseek")
        tools: Optional list of tools in OpenAI format
        tool_choice: Optional tool choice ("auto", "required", "none", or specific tool)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds

    Returns:
        ModelResponse with unified structure
    """
    handler = PROVIDERS.get(provider)

    if not handler:
        raise ValueError(f"Unknown provider: {provider}")

    api_key = os.environ.get(handler.key_env)
    if not api_key:
        raise ValueError(f"{handler.key_env} not found in environment variables")

    headers = handler.headers(api_key)
    body = handler.build_request(model, messages, tools, tool_choice, max_tokens)

    with httpx.Client(timeout=timeout) as client:
        response = client.post(handler.endpoint, headers=headers, json=body)
        response.raise_for_status()

    return handler.parse_response(response.json())
