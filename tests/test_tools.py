from __future__ import annotations

import asyncio
import json

import httpx

from local_llm_gateway.models import CanonicalRequest, ProtocolName, ProviderTarget
from local_llm_gateway.protocols import (
    anthropic_tool_choice_to_provider,
    anthropic_tools_to_provider,
    canonical_messages_to_provider,
    content_to_text,
    provider_tool_calls_to_content,
)
from local_llm_gateway.providers.ollama import OllamaAdapter
from local_llm_gateway.providers.vllm import VllmAdapter
from local_llm_gateway.streaming import ollama_line_stream_to_sse, openai_stream_to_sse

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather",
        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
    }
]


def _target(provider: str = "ollama") -> ProviderTarget:
    return ProviderTarget(provider=provider, model="m", base_url="http://mock")


def _request(messages: list[dict], tools: list[dict] | None = None) -> CanonicalRequest:
    return CanonicalRequest(
        request_id="r1",
        protocol=ProtocolName.anthropic,
        model="m",
        messages=messages,
        tools=tools or [],
    )


# ---------- request-side conversion ----------


def test_tools_schema_converted_to_openai_function_format():
    converted = anthropic_tools_to_provider(TOOLS)

    assert converted == [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            },
        }
    ]


def test_tool_choice_converted_to_provider_vocabulary():
    assert anthropic_tool_choice_to_provider({"type": "auto"}) == "auto"
    assert anthropic_tool_choice_to_provider({"type": "any"}) == "required"
    assert anthropic_tool_choice_to_provider(
        {"type": "tool", "name": "get_weather"}
    ) == {
        "type": "function",
        "function": {"name": "get_weather"},
    }
    assert anthropic_tool_choice_to_provider("any") == "required"
    assert anthropic_tool_choice_to_provider(None) is None


def test_canonical_messages_convert_tool_use_and_result_openai_style():
    messages = [
        {"role": "user", "content": "weather in Shanghai?"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "let me check"},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {"city": "Shanghai"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "sunny 26C",
                }
            ],
        },
    ]

    converted = canonical_messages_to_provider(messages, style="openai")

    assert converted[0] == {"role": "user", "content": "weather in Shanghai?"}
    assistant = converted[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "let me check"
    assert assistant["tool_calls"][0]["id"] == "toolu_1"
    assert assistant["tool_calls"][0]["type"] == "function"
    assert assistant["tool_calls"][0]["function"]["name"] == "get_weather"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {
        "city": "Shanghai"
    }
    assert converted[2] == {
        "role": "tool",
        "tool_call_id": "toolu_1",
        "content": "sunny 26C",
    }


def test_canonical_messages_convert_ollama_style_keeps_dict_arguments():
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {"city": "Shanghai"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "sunny"}
            ],
        },
    ]

    converted = canonical_messages_to_provider(messages, style="ollama")

    assert converted[0]["tool_calls"][0]["function"]["arguments"] == {
        "city": "Shanghai"
    }
    assert converted[1] == {"role": "tool", "content": "sunny"}


def test_plain_messages_pass_through_unchanged():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    converted = canonical_messages_to_provider(messages, style="openai")

    assert converted == messages


# ---------- response-side conversion ----------


def test_provider_tool_calls_with_string_arguments_parse_json():
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"city": "Shanghai"}'},
        }
    ]

    blocks = provider_tool_calls_to_content(tool_calls, style="openai")

    assert blocks == [
        {
            "type": "tool_use",
            "id": "call_1",
            "name": "get_weather",
            "input": {"city": "Shanghai"},
        }
    ]


def test_provider_tool_calls_with_dict_arguments_ollama_style():
    tool_calls = [
        {"function": {"name": "get_weather", "arguments": {"city": "Shanghai"}}}
    ]

    blocks = provider_tool_calls_to_content(tool_calls, style="ollama")

    assert blocks[0]["type"] == "tool_use"
    assert blocks[0]["name"] == "get_weather"
    assert blocks[0]["input"] == {"city": "Shanghai"}
    assert blocks[0]["id"].startswith("toolu_")


def test_invalid_json_arguments_kept_as_raw():
    tool_calls = [{"function": {"name": "get_weather", "arguments": "{broken"}}]

    blocks = provider_tool_calls_to_content(tool_calls, style="openai")

    assert blocks[0]["input"] == {"_raw": "{broken"}


def test_content_to_text_includes_tool_result_text():
    content = [
        {
            "type": "tool_result",
            "tool_use_id": "t1",
            "content": [{"type": "text", "text": "result data"}],
        }
    ]

    assert content_to_text(content) == "result data"


# ---------- streaming with tool calls ----------


def test_ollama_stream_emits_tool_use_events():
    async def _collect() -> bytes:
        async def _lines():
            yield json.dumps({"message": {"content": "checking"}, "done": False})
            yield json.dumps(
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {"city": "Shanghai"},
                                }
                            }
                        ]
                    },
                    "done": False,
                }
            )
            yield json.dumps(
                {
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 12,
                    "eval_count": 4,
                }
            )

        chunks = []
        async for chunk in ollama_line_stream_to_sse(
            _lines(), _target(), "msg_t", input_tokens_estimate=10
        ):
            chunks.append(chunk)
        return b"".join(chunks)

    out = asyncio.run(_collect()).decode()

    # text delta flows through
    assert "checking" in out
    # tool_use block start / input json delta / stop emitted in order
    assert out.index(
        "content_block_stop", out.index("content_block_delta")
    ) < out.index('"type":"tool_use"')
    assert '"type":"input_json_delta"' in out
    assert '"partial_json":"' in out
    # stop reason forced to tool_use
    assert '"stop_reason":"tool_use"' in out
    # input tokens from prompt_eval_count reported in message_delta
    assert '"input_tokens":12' in out


def test_openai_stream_emits_tool_use_events_and_estimates_input_tokens():
    async def _collect() -> bytes:
        async def _lines():
            yield "data: " + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_weather",
                                            "arguments": '{"ci',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            yield "data: " + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": 'ty": "Shanghai"}'},
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ]
                }
            )
            yield "data: " + json.dumps(
                {
                    "choices": [{"delta": {}, "finish_reason": "tool_calls"}],
                    "usage": {"prompt_tokens": 8, "completion_tokens": 3},
                }
            )
            yield "data: [DONE]"

        chunks = []
        async for chunk in openai_stream_to_sse(
            _lines(), _target("vllm"), "msg_t", input_tokens_estimate=5
        ):
            chunks.append(chunk)
        return b"".join(chunks)

    out = asyncio.run(_collect()).decode()

    assert '"type":"tool_use"' in out
    assert '"input_json_delta"' in out
    assert '"stop_reason":"tool_use"' in out
    # usage from final chunk wins over estimate
    assert '"input_tokens":8' in out
    assert '"output_tokens":3' in out


def test_message_start_reports_input_token_estimate():
    async def _collect() -> bytes:
        async def _lines():
            yield json.dumps(
                {
                    "message": {"content": "hi"},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 0,
                    "eval_count": 1,
                }
            )

        chunks = []
        async for chunk in ollama_line_stream_to_sse(
            _lines(), _target(), "msg_t", input_tokens_estimate=42
        ):
            chunks.append(chunk)
        return chunks[0]

    first = asyncio.run(_collect())

    assert b'"input_tokens":42' in first


# ---------- non-streaming adapters with tool calls ----------


def test_ollama_create_message_converts_tool_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": {"city": "Shanghai"},
                            }
                        }
                    ],
                },
                "done": True,
                "prompt_eval_count": 10,
                "eval_count": 2,
            },
        )

    adapter = OllamaAdapter()

    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            resp = await adapter.create_message(client, _target(), _request([], TOOLS))
            assert resp.content[0]["type"] == "tool_use"
            assert resp.content[0]["name"] == "get_weather"
            assert resp.content[0]["input"] == {"city": "Shanghai"}
            assert resp.stop_reason == "tool_calls"

    asyncio.run(go())


def test_ollama_payload_carries_converted_tools_and_history():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": "ok"}, "done": True}
        )

    messages = [
        {"role": "user", "content": "weather?"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {"city": "Shanghai"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "sunny"}
            ],
        },
    ]

    async def go() -> None:
        adapter = OllamaAdapter()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await adapter.create_message(
                client,
                _target(),
                _request(messages, TOOLS),
            )

    asyncio.run(go())

    payload = captured["payload"]
    assert payload["tools"][0]["function"]["name"] == "get_weather"
    assert payload["tools"][0]["function"]["parameters"]["type"] == "object"
    assert payload["tool_choice"] == "auto"
    assert payload["messages"][1]["tool_calls"][0]["function"]["arguments"] == {
        "city": "Shanghai"
    }
    assert payload["messages"][2] == {"role": "tool", "content": "sunny"}


def test_vllm_create_message_converts_tool_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"city": "Shanghai"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 9, "completion_tokens": 2},
            },
        )

    adapter = VllmAdapter()

    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            resp = await adapter.create_message(
                client, _target("vllm"), _request([], TOOLS)
            )
            assert resp.content[0] == {
                "type": "tool_use",
                "id": "call_1",
                "name": "get_weather",
                "input": {"city": "Shanghai"},
            }
            assert resp.stop_reason == "tool_calls"
            assert resp.usage.input_tokens == 9

    asyncio.run(go())
