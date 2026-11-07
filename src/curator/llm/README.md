# llm
Owns: starting llama.cpp's `llama-server` with the local model (Gemma 4 26B-A4B by default, file from `$CURATOR_MODEL` or `model.gguf` next to the database), one schema-constrained chat call, stopping it again. A server already running on 127.0.0.1:8099 is used and left running.
Must not: run SQL, read the library, build prompts or decide picks (that's `curator.picks`). Talks only to 127.0.0.1. Any failure raises `LlmError`.
Entry point: `with LocalModel(path) as m: m.chat(messages, schema)`.
