from __future__ import annotations

from ..models import CanonicalRequest, MessageRequest, ProtocolName, SamplingParams


class AnthropicFacade:
    protocol = ProtocolName.anthropic

    def to_canonical(self, request: MessageRequest, request_id: str) -> CanonicalRequest:
        return CanonicalRequest(
            request_id=request_id,
            protocol=self.protocol,
            model=request.model,
            messages=request.messages,
            system=request.system,
            max_tokens=request.max_tokens,
            stream=request.stream,
            sampling=SamplingParams(
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                stop_sequences=request.stop_sequences or [],
            ),
            tools=request.tools or [],
            tool_choice=request.tool_choice,
            metadata=request.metadata or {},
            stream_options=request.stream_options or {},
        )
