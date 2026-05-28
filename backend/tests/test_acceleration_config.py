import sys
from types import SimpleNamespace

from backend.app.services.embeddings import FastEmbedProvider


def test_fastembed_receives_selected_onnx_execution_provider(monkeypatch) -> None:
    captured = {}

    class FakeEmbedding:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def embed(self, texts):
            del texts
            return iter([[0.0, 1.0, 0.0]])

    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=FakeEmbedding))

    provider = FastEmbedProvider(
        "intfloat/multilingual-e5-large",
        "OpenVINOExecutionProvider",
        threads=2,
    )

    assert provider.dimension == 3
    assert captured["providers"] == ["OpenVINOExecutionProvider"]
    assert captured["threads"] == 2
