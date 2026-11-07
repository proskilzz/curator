"""The local model (llama-server on 127.0.0.1). See README.md."""

from curator.llm.server import LlmError, LocalModel, default_model_path

__all__ = ["LlmError", "LocalModel", "default_model_path"]
