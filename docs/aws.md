# Running SkillBridge on AWS (optional)

SkillBridge needs no GPU, so it runs on a small CPU-only EC2 instance using a
quantized open-weight model served by [llama.cpp](https://github.com/ggerganov/llama.cpp).
This is an optional tie-in; the default path is local Ollama.

## 1. Launch a CPU instance

- Instance type: `t3.large` or `c7g.large` (ARM Graviton) is enough for a
  1-4B quantized model.
- OS: Amazon Linux 2023 or Ubuntu 22.04.
- Storage: 20 GB is comfortable for one quantized model plus the repo.

## 2. Serve the model with llama.cpp

```bash
# Build llama.cpp with its OpenAI-compatible server
git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp
cmake -B build && cmake --build build --config Release

# Download a small Apache-2.0 / MIT GGUF (example: a Qwen3-4B quant)
# then start the server with grammar/JSON support:
./build/bin/llama-server -m models/qwen3-4b.gguf --port 11434 --host 0.0.0.0
```

## 3. Point SkillBridge at it

`OllamaBackend` targets `http://localhost:11434` by default. For a different
host, set `OLLAMA_HOST`:

```bash
export OLLAMA_HOST="http://<ec2-private-ip>:11434"
skillbridge run "find me beginner issues in Python"
```

A llama.cpp server exposes a compatible chat endpoint and supports grammar
constrained output, which maps onto SkillBridge's schema-constrained actions.
If a given server build does not support schema enforcement, SkillBridge falls
back to JSON mode plus verifier retries (see Risks and Fallbacks in the SPEC).

## Cost and safety notes

- Stop or terminate the instance when idle; a small CPU instance is cheap but
  not free.
- The harness still enforces its sandbox (path confinement, URL allowlist,
  script timeout) regardless of where the model runs.
- Keep any `GITHUB_TOKEN` in the instance environment or a secrets manager,
  never in the repo.
