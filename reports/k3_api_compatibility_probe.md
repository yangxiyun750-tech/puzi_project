# K3 API Compatibility Probe Report

- **Date**: 2026-08-17T17:07:21.816504+00:00
- **Endpoint**: `https://duoyuanx.com/v1/chat/completions`
- **Model ID tested**: `kimi-k3`
- **API Key**: present in environment (not logged)

## Summary

| Probe | Description | HTTP Status | Latency (ms) | Success |
|-------|-------------|-------------|--------------|---------|
| A | model + messages only | 200 | 6179.4 | ✅ |
| B | A + response_format={type: json_object} | 200 | 2722.6 | ✅ |
| C | A + temperature=0.0 + max_tokens=1024 | 200 | 2430.0 | ✅ |
| D | A + enable_thinking=false (current extra_body for kimi) | 200 | 9148.8 | ✅ |
| E | Full production request (system prompt + user text + temperature + max_tokens + response_format + enable_thinking) | 200 | 2440.6 | ✅ |

**Conclusion**: All probes succeeded. The model works with the current relay using the tested model id.

## Detailed Probe Results

### Probe A: model + messages only

- **HTTP Status**: 200
- **Exception Type**: `None`
- **Is Timeout**: False
- **Response Body Empty**: False
- **Latency**: 6179.4 ms
- **Fields Used**: `messages`, `model`

**Response body**:
```json
{"id":"be028c9e-87e6-4312-a339-46547a98eb55","object":"chat.completion","created":1786986424,"model":"moonshotai/Kimi-K3","choices":[{"index":0,"message":{"role":"assistant","content":"```json\n{\"status\": \"ok\"}\n```","reasoning_content":"The user wants me to return a simple JSON object: {\"status\": \"ok\"}. This is a straightforward request. I should just output the JSON object. Since they've asked for JSON, I might want to format it as a code block or just plain JSON. Let me think about the format - they said \"Return the JSON object\" so I should just return it. A code block with json syntax highlighting would be appropriate for clarity.","tool_calls":null},"logprobs":null,"finish_reason":"stop","matched_stop":163586}],"usage":{"prompt_tokens":96,"total_tokens":207,"completion_tokens":111,"prompt_tokens_details":{"cached_tokens":64},"reasoning_tokens":91},"metadata":{"weight_version":"default"}}
```

**Error body**:
*(empty)*

---

### Probe B: A + response_format={type: json_object}

- **HTTP Status**: 200
- **Exception Type**: `None`
- **Is Timeout**: False
- **Response Body Empty**: False
- **Latency**: 2722.6 ms
- **Fields Used**: `messages`, `model`, `response_format`

**Response body**:
```json
{"id":"e34c792b-bccc-43c1-9df9-d66388c73853","object":"chat.completion","created":1786986427,"model":"moonshotai/Kimi-K3","choices":[{"index":0,"message":{"role":"assistant","content":"{\"status\": \"ok\"}","reasoning_content":"The user wants me to return the JSON object {\"status\": \"ok\"}. The response format is already set to json_object, so I just need to return that exact JSON.","tool_calls":null},"logprobs":null,"finish_reason":"stop","matched_stop":163586}],"usage":{"prompt_tokens":143,"total_tokens":189,"completion_tokens":46,"prompt_tokens_details":{"cached_tokens":64},"reasoning_tokens":39},"metadata":{"weight_version":"default"}}
```

**Error body**:
*(empty)*

---

### Probe C: A + temperature=0.0 + max_tokens=1024

- **HTTP Status**: 200
- **Exception Type**: `None`
- **Is Timeout**: False
- **Response Body Empty**: False
- **Latency**: 2430.0 ms
- **Fields Used**: `max_tokens`, `messages`, `model`, `temperature`

**Response body**:
```json
{"id":"c0a62142-8418-4fe9-8a8c-e5c3dbe2287a","object":"chat.completion","created":1786986430,"model":"moonshotai/Kimi-K3","choices":[{"index":0,"message":{"role":"assistant","content":"```json\n{\"status\": \"ok\"}\n```","reasoning_content":"The user is asking me to return a JSON object. This is a simple, benign request. I should just return the JSON object as requested.","tool_calls":null},"logprobs":null,"finish_reason":"stop","matched_stop":163586}],"usage":{"prompt_tokens":96,"total_tokens":148,"completion_tokens":52,"prompt_tokens_details":{"cached_tokens":64},"reasoning_tokens":32},"metadata":{"weight_version":"default"}}
```

**Error body**:
*(empty)*

---

### Probe D: A + enable_thinking=false (current extra_body for kimi)

- **HTTP Status**: 200
- **Exception Type**: `None`
- **Is Timeout**: False
- **Response Body Empty**: False
- **Latency**: 9148.8 ms
- **Fields Used**: `enable_thinking`, `messages`, `model`

**Response body**:
```json
{"id":"4b142e69-5670-4cca-83c5-d9b77274239a","object":"chat.completion","created":1786986433,"model":"moonshotai/Kimi-K3","choices":[{"index":0,"message":{"role":"assistant","content":"```json\n{\"status\": \"ok\"}\n```","reasoning_content":"The user is asking me to return a JSON object. This is a simple, direct request. I should just return the JSON object as requested.\n\nThe format: they're asking for a specific JSON object. I could return it as plain text or in a code block. Since they specifically asked for the JSON object itself, I should return it cleanly. A code block with json formatting would be appropriate here, or I could just return the raw JSON.\n\nSince they want exactly that JSON object returned, I'll provide it in a JSON code block for clarity.","tool_calls":null},"logprobs":null,"finish_reason":"stop","matched_stop":163586}],"usage":{"prompt_tokens":96,"total_tokens":228,"completion_tokens":132,"prompt_tokens_details":{"cached_tokens":64},"reasoning_tokens":112},"metadata":{"weight_version":"default"}}
```

**Error body**:
*(empty)*

---

### Probe E: Full production request (system prompt + user text + temperature + max_tokens + response_format + enable_thinking)

- **HTTP Status**: 200
- **Exception Type**: `None`
- **Is Timeout**: False
- **Response Body Empty**: False
- **Latency**: 2440.6 ms
- **Fields Used**: `enable_thinking`, `max_tokens`, `messages`, `model`, `response_format`, `temperature`

**Response body**:
```json
{"id":"2aa673d7-e851-44ac-a9c9-44d66a523851","object":"chat.completion","created":1786986441,"model":"moonshotai/Kimi-K3","choices":[{"index":0,"message":{"role":"assistant","content":"{\"action\":\"transpose\",\"scope\":\"all\",\"direction\":\"up\",\"interval\":\"major_second\",\"semitones\":2}","reasoning_content":"The user is asking me to parse a music-score transpose request into JSON. The request is in Chinese: \"把整首升大二度\" which means \"transpose the whole piece up by a major second.\"\n\nLet me break this down:\n- 把整首 = the whole piece/entire song\n- 升 = raise/up (sharp)\n- 大二度 = major second (interval)\n\nSo the intent is:\n- scope: entire piece / all\n- direction: up\n- interval: major second (2 semitones)\n\nI should return a JSON object representing this transpose request. A reasonable schema might be:\n\n{\n  \"action\": \"transpose\",\n  \"scope\": \"all\",\n  \"direction\": \"up\",\n  \"interval\": \"major_second\",\n  \"semitones\": 2\n}\n\nLet me think about what fields make sense:\n- action: \"transpose\"\n- scope: \"whole\" or \"all\" (整首 = whole piece)\n- direction: \"up\" (升 = raise)\n- interval: \"major second\" (大二度)\n- semitones: 2\n\nI'll return a clean JSON 
... [truncated]
```

**Error body**:
*(empty)*

---

## Recommendations

- K3 works with the current relay and model id.
- No changes to `OpenAICompatibleClient` are required for basic connectivity.
- Validate the full `run_real_provider_reliability.py` run to confirm end-to-end behavior.
