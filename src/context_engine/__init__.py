"""Core contracts. Importing this package performs no configuration or network I/O."""

__version__ = "0.17.1"


def __getattr__(name):
    """Expose the real typed API lazily, without loading tokenizers on package import."""
    if name in ("assemble_context", "AssembledContext", "AssemblyOptions"):
        from . import pipeline

        return getattr(pipeline, name)
    if name in ("ChatMemory", "AsyncChatMemory"):
        from . import chat_memory

        return getattr(chat_memory, name)
    raise AttributeError(name)


__all__ = [
    "assemble_context",
    "AssembledContext",
    "AssemblyOptions",
    "AsyncChatMemory",
    "ChatMemory",
    "__version__",
]
