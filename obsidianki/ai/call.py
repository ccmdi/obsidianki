"""
lite_llm.py - Minimal LLM wrapper (~130ms import)

Supports: OpenAI, Anthropic, Google (Gemini), DeepSeek
No streaming. Tool calling supported.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import httpx

# Provider endpoints
ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
}

# Environment variable names for API keys
API_KEY_NAMES = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


@dataclass
class Function:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    type: str
    function: Function


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


def _get_provider(model: str) -> tuple[str, str]:
    """Extract provider and model name from model string like 'openai/gpt-4'"""
    if "/" in model:
        parts = model.split("/", 1)
        provider = parts[0]
        model_name = parts[1]

        # Handle nested paths like "gemini/gemini-2.5-pro"
        if provider == "gemini":
            provider = "google"

        return provider, model_name

    # Guess provider from model name
    if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        return "openai", model
    elif model.startswith("claude"):
        return "anthropic", model
    elif model.startswith("gemini"):
        return "google", model
    elif model.startswith("deepseek"):
        return "deepseek", model

    raise ValueError(f"Cannot determine provider for model: {model}")


def _get_api_key(provider: str) -> str:
    """Get API key from environment"""
    key_name = API_KEY_NAMES.get(provider)
    if not key_name:
        raise ValueError(f"Unknown provider: {provider}")

    key = os.environ.get(key_name)
    if not key:
        raise ValueError(f"{key_name} not found in environment variables")

    return key


def _build_headers(provider: str, api_key: str) -> Dict[str, str]:
    """Build request headers for each provider"""
    if provider == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    elif provider == "google":
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        # OpenAI-compatible (openai, deepseek)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }


def _convert_tools_for_anthropic(tools: List[Dict]) -> List[Dict]:
    """Convert OpenAI tool format to Anthropic format"""
    anthropic_tools = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool["function"]
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
    return anthropic_tools


def _convert_tool_choice_for_anthropic(tool_choice: Union[str, Dict]) -> Dict:
    """Convert OpenAI tool_choice to Anthropic format"""
    if tool_choice == "auto":
        return {"type": "auto"}
    elif tool_choice == "required":
        return {"type": "any"}
    elif tool_choice == "none":
        return {"type": "none"}
    elif isinstance(tool_choice, dict):
        # {"type": "function", "function": {"name": "..."}}
        return {"type": "tool", "name": tool_choice["function"]["name"]}
    return {"type": "auto"}


def _build_anthropic_request(
    model: str,
    messages: List[Dict],
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None,
    max_tokens: int = 4096,
    **kwargs
) -> Dict:
    """Build Anthropic API request body"""
    # Extract system message
    system = None
    chat_messages = []

    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        else:
            chat_messages.append(msg)

    body: Dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": max_tokens,
    }

    if system:
        body["system"] = system

    if tools:
        body["tools"] = _convert_tools_for_anthropic(tools)
        if tool_choice:
            body["tool_choice"] = _convert_tool_choice_for_anthropic(tool_choice)

    return body


def _parse_anthropic_response(response_json: Dict) -> ModelResponse:
    """Convert Anthropic response to OpenAI-compatible ModelResponse"""
    content_blocks = response_json.get("content", [])

    # Extract text content
    text_content = None
    tool_calls = []

    for i, block in enumerate(content_blocks):
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

    message = Message(
        role="assistant",
        content=text_content,
        tool_calls=tool_calls if tool_calls else None,
    )

    usage_data = response_json.get("usage", {})
    usage = Usage(
        prompt_tokens=usage_data.get("input_tokens", 0),
        completion_tokens=usage_data.get("output_tokens", 0),
        total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
    )

    return ModelResponse(
        id=response_json.get("id", ""),
        object="chat.completion",
        created=0,
        model=response_json.get("model", ""),
        choices=[Choice(index=0, message=message, finish_reason=response_json.get("stop_reason"))],
        usage=usage,
    )


def _parse_openai_response(response_json: Dict) -> ModelResponse:
    """Convert OpenAI-compatible response to ModelResponse"""
    choices = []

    for i, choice_data in enumerate(response_json.get("choices", [])):
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

        message = Message(
            role=msg_data.get("role", "assistant"),
            content=msg_data.get("content"),
            tool_calls=tool_calls,
        )

        choices.append(Choice(
            index=i,
            message=message,
            finish_reason=choice_data.get("finish_reason"),
        ))

    usage_data = response_json.get("usage", {})
    usage = Usage(
        prompt_tokens=usage_data.get("prompt_tokens", 0),
        completion_tokens=usage_data.get("completion_tokens", 0),
        total_tokens=usage_data.get("total_tokens", 0),
    )

    return ModelResponse(
        id=response_json.get("id", ""),
        object=response_json.get("object", "chat.completion"),
        created=response_json.get("created", 0),
        model=response_json.get("model", ""),
        choices=choices,
        usage=usage,
    )


def completion(
    model: str,
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None,
    max_tokens: int = 4096,
    timeout: float = 120.0,
    **kwargs
) -> ModelResponse:
    """
    Unified completion API for multiple providers.

    Args:
        model: Model identifier (e.g., "openai/gpt-4", "claude-sonnet-4-5", "gemini/gemini-2.5-pro")
        messages: List of message dicts with 'role' and 'content'
        tools: Optional list of tools in OpenAI format
        tool_choice: Optional tool choice ("auto", "required", "none", or specific tool)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        **kwargs: Additional provider-specific parameters

    Returns:
        ModelResponse with OpenAI-compatible structure
    """
    provider, model_name = _get_provider(model)
    api_key = _get_api_key(provider)
    endpoint = ENDPOINTS[provider]
    headers = _build_headers(provider, api_key)

    if provider == "anthropic":
        body = _build_anthropic_request(
            model=model_name,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            **kwargs
        )
    else:
        # OpenAI-compatible providers
        token_param = "max_completion_tokens" if provider == "openai" else "max_tokens"
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            token_param: max_tokens,
        }
        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice

    with httpx.Client(timeout=timeout) as client:
        response = client.post(endpoint, headers=headers, json=body)
        response.raise_for_status()
        response_json = response.json()

    if provider == "anthropic":
        return _parse_anthropic_response(response_json)
    else:
        return _parse_openai_response(response_json)
