"""
Monkey-patch for crewai 1.9.3 + Anthropic API incompatibility.

crewai's handle_max_iterations_exceeded() appends an assistant-role message
then immediately calls the LLM, but Anthropic requires the conversation to
end with a user message. This patch strips trailing assistant messages from
the input list before the Anthropic provider processes them.
"""

from crewai.llms.providers.anthropic.completion import AnthropicCompletion

_original_format = AnthropicCompletion._format_messages_for_anthropic


def _patched_format(self, messages):
    # Strip trailing assistant messages so Anthropic never sees a prefill
    if isinstance(messages, list):
        while messages and messages[-1].get("role") == "assistant":
            messages = messages[:-1]
    return _original_format(self, messages)


AnthropicCompletion._format_messages_for_anthropic = _patched_format
