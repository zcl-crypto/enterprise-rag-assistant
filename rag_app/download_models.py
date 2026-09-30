from __future__ import annotations

import os
from pathlib import Path


def download_embedding_model() -> Path:
    from modelscope import snapshot_download

    target = Path(os.getenv("EMBEDDING_MODEL_PATH", ".models/bge-small-zh-v1.5"))
    if (target / "modules.json").is_file() and (target / "pytorch_model.bin").is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download("Xorbits/bge-small-zh-v1.5", local_dir=str(target))
    if not (target / "pytorch_model.bin").is_file():
        raise RuntimeError("Embedding model download did not produce weights")
    return target


def download_reranker_model() -> Path:
    from modelscope import snapshot_download

    target = Path(os.getenv("RERANKER_MODEL_PATH", ".models/bge-reranker-base"))
    if (target / "model.safetensors").is_file() and (target / "tokenizer.json").is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        "BAAI/bge-reranker-base",
        local_dir=str(target),
        allow_patterns=[
            "model.safetensors", "config.json", "configuration.json", "tokenizer.json",
            "tokenizer_config.json", "special_tokens_map.json", "sentencepiece.bpe.model",
        ],
    )
    if not (target / "model.safetensors").is_file():
        raise RuntimeError("Reranker model download did not produce weights")
    return target


if __name__ == "__main__":
    print(download_embedding_model())
    if os.getenv("RETRIEVAL_MODE") == "hybrid":
        from rag_app.lexical_index import ChineseBm25

        ChineseBm25()
        print("BM25 model cached")
    if os.getenv("ENABLE_RERANKER") == "1":
        print(download_reranker_model())
