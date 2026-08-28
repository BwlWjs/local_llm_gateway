#!/bin/bash
# End-to-end tool_use round-trip: Claude (Anthropic schema) -> ModelRelay
# gateway -> Ollama qwen3:8b -> tool_use content block back.
# Uses stream:false for a clean JSON response. Exit 0 = tool call succeeded.
set -euo pipefail

KEY="${MODELRELAY_KEY:-$(cat /tmp/mr_key.txt 2>/dev/null)}"
BASE="${MODELRELAY_BASE:-http://127.0.0.1:8000}"
MODEL="${MODELRELAY_MODEL:-qwen3-8b}"

if [ -z "$KEY" ]; then
  echo "ERROR: no API key (set MODELRELAY_KEY or /tmp/mr_key.txt)" >&2
  exit 3
fi

curl -s --noproxy '*' --max-time 120 -X POST "${BASE}/v1/messages" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"${MODEL}\",
    \"max_tokens\": 512,
    \"stream\": false,
    \"tools\": [{
      \"name\": \"get_weather\",
      \"description\": \"Get current weather for a city\",
      \"input_schema\": {\"type\":\"object\",\"properties\":{\"city\":{\"type\":\"string\",\"description\":\"City name\"}},\"required\":[\"city\"]}
    }],
    \"messages\": [
      {\"role\": \"user\", \"content\": \"What is the weather in Beijing? You MUST use the get_weather tool.\"}
    ]
  }" | /Users/lucas/.workbuddy/binaries/python/envs/default/bin/python -c "
import sys, json
d = json.load(sys.stdin)
print('stop_reason:', d.get('stop_reason'))
for b in d.get('content', []):
    print(' ', b.get('type'), '-', {k:v for k,v in b.items() if k!='type'})
tus = [b for b in d.get('content', []) if b.get('type')=='tool_use']
if tus and tus[0]['name']=='get_weather':
    print('PASS: tool_use round-trip OK ->', tus[0]['name'], tus[0]['input'])
    sys.exit(0)
print('FAIL: no get_weather tool_use in response')
sys.exit(1)
"
