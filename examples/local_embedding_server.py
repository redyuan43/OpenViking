#!/usr/bin/env python3
"""Local OpenAI-compatible embedding service for OpenViking."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, List

import torch
import torch.nn.functional as F
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from transformers import AutoModel, AutoTokenizer

DEFAULT_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "intfloat/multilingual-e5-base")
DEFAULT_DEVICE = os.environ.get("LOCAL_EMBED_DEVICE", "auto")
DEFAULT_BATCH_SIZE = int(os.environ.get("LOCAL_EMBED_BATCH_SIZE", "16"))
DEFAULT_MAX_LENGTH = int(os.environ.get("LOCAL_EMBED_MAX_LENGTH", "512"))
DEFAULT_API_KEY = os.environ.get("LOCAL_EMBED_API_KEY", "local")
DEFAULT_MODEL_REVISION = os.environ.get("LOCAL_EMBED_REVISION")
DEFAULT_TRUST_REMOTE_CODE = os.environ.get("LOCAL_EMBED_TRUST_REMOTE_CODE", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

QUERY_TYPES = {"query", "search_query", "retrieval.query", "retrieval_query"}
DOCUMENT_TYPES = {"passage", "document", "search_document", "retrieval.passage", "retrieval_document"}


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    input: str | List[str]
    model: str | None = Field(default=None)
    input_type: str | None = Field(default=None)
    dimensions: int | None = Field(default=None)


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "local"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelCard]


def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    masked = last_hidden_state * mask
    summed = masked.sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def _as_texts(value: str | List[str]) -> List[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _apply_input_type(texts: Iterable[str], input_type: str | None) -> List[str]:
    if input_type in QUERY_TYPES:
        return [f"query: {text}" for text in texts]
    if input_type in DOCUMENT_TYPES:
        return [f"passage: {text}" for text in texts]
    return [str(text) for text in texts]


@dataclass
class EmbeddingEngine:
    model_name: str
    tokenizer: Any
    model: Any
    device: str
    batch_size: int
    max_length: int
    dimension: int

    @classmethod
    def load(
        cls,
        model_name: str,
        *,
        device: str = DEFAULT_DEVICE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_length: int = DEFAULT_MAX_LENGTH,
        revision: str | None = DEFAULT_MODEL_REVISION,
    ) -> "EmbeddingEngine":
        resolved_device = device
        if resolved_device == "auto":
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"

        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            trust_remote_code=DEFAULT_TRUST_REMOTE_CODE,
        )
        model_kwargs: dict[str, Any] = {
            "revision": revision,
            "trust_remote_code": DEFAULT_TRUST_REMOTE_CODE,
        }
        if resolved_device == "cuda":
            model_kwargs["torch_dtype"] = torch.float16
        model = AutoModel.from_pretrained(model_name, **model_kwargs)
        model.to(resolved_device)
        model.eval()

        with torch.inference_mode():
            sample = tokenizer(
                ["passage: hello world"],
                padding=True,
                truncation=True,
                max_length=max(max_length, 64),
                return_tensors="pt",
            )
            sample = {key: value.to(resolved_device) for key, value in sample.items()}
            outputs = model(**sample)
            pooled = _mean_pool(outputs.last_hidden_state, sample["attention_mask"])
            pooled = F.normalize(pooled, p=2, dim=1)
            dimension = int(pooled.shape[-1])

        return cls(
            model_name=model_name,
            tokenizer=tokenizer,
            model=model,
            device=resolved_device,
            batch_size=max(batch_size, 1),
            max_length=max(max_length, 64),
            dimension=dimension,
        )

    @torch.inference_mode()
    def embed(self, texts: List[str], input_type: str | None = None) -> List[List[float]]:
        normalized_texts = _apply_input_type(texts, input_type)
        vectors: List[List[float]] = []

        for start in range(0, len(normalized_texts), self.batch_size):
            batch_texts = normalized_texts[start : start + self.batch_size]
            encoded = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            outputs = self.model(**encoded)
            pooled = _mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
            pooled = F.normalize(pooled, p=2, dim=1)
            vectors.extend(pooled.float().detach().cpu().tolist())

        return vectors


app = FastAPI(title="Local Embedding Service", version="0.1.0")
ENGINE = EmbeddingEngine.load(DEFAULT_MODEL)


def _check_api_key(authorization: str | None) -> None:
    if not DEFAULT_API_KEY:
        return
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {DEFAULT_API_KEY}"
    if authorization.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/healthz")
def healthz() -> dict[str, str | int]:
    return {
        "status": "ok",
        "model": ENGINE.model_name,
        "device": ENGINE.device,
        "dimension": ENGINE.dimension,
    }


@app.get("/v1/models", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    return ModelsResponse(data=[ModelCard(id=ENGINE.model_name)])


@app.post("/v1/embeddings")
def embeddings(request: EmbeddingRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_api_key(authorization)

    requested_model = request.model or ENGINE.model_name
    if requested_model != ENGINE.model_name:
        raise HTTPException(
            status_code=400,
            detail=f"Loaded model is {ENGINE.model_name}, request asked for {requested_model}",
        )

    if request.dimensions is not None and request.dimensions != ENGINE.dimension:
        raise HTTPException(
            status_code=400,
            detail=f"Loaded model dimension is {ENGINE.dimension}, request asked for {request.dimensions}",
        )

    texts = _as_texts(request.input)
    vectors = ENGINE.embed(texts, input_type=request.input_type)
    data = [
        {
            "object": "embedding",
            "index": index,
            "embedding": vector,
        }
        for index, vector in enumerate(vectors)
    ]

    prompt_tokens = sum(max(len(text) // 4, 1) for text in texts)
    return {
        "object": "list",
        "data": data,
        "model": ENGINE.model_name,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": prompt_tokens,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("LOCAL_EMBED_HOST", "127.0.0.1"),
        port=int(os.environ.get("LOCAL_EMBED_PORT", "8766")),
    )
