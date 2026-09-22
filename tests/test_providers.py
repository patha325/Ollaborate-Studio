from ollaborate_studio.providers import OpenAICompatibleClient


def test_tool_schema_uses_signature_and_docstring() -> None:
    def find(query: str, limit: int = 3) -> list[str]:
        """Find project text."""
        return []

    schema = OpenAICompatibleClient._tool_schema(find)
    function = schema["function"]
    assert function["name"] == "find"
    assert function["description"] == "Find project text."
    assert function["parameters"]["required"] == ["query"]
    assert function["parameters"]["properties"]["limit"]["type"] == "integer"


def test_tool_messages_receive_matching_call_id() -> None:
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "find", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_name": "find", "content": "result"},
    ]
    converted = OpenAICompatibleClient._messages(messages)
    assert converted[1]["tool_call_id"] == "call-1"
    assert converted[1]["name"] == "find"
