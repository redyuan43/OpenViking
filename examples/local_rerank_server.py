#!/usr/bin/env python3
"""Local OpenAI-compatible rerank service for OpenViking."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

DEFAULT_MODEL = os.environ.get(
    "LOCAL_RERANK_MODEL", "Alibaba-NLP/gte-multilingual-reranker-base"
)
DEFAULT_DEVICE = os.environ.get("LOCAL_RERANK_DEVICE", "auto")
DEFAULT_BATCH_SIZE = int(os.environ.get("LOCAL_RERANK_BATCH_SIZE", "8"))
DEFAULT_MAX_LENGTH = int(os.environ.get("LOCAL_RERANK_MAX_LENGTH", "1024"))
DEFAULT_API_KEY = os.environ.get("LOCAL_RERANK_API_KEY", "local")
DEFAULT_MODEL_REVISION = os.environ.get("LOCAL_RERANK_REVISION")
DEFAULT_TRUST_REMOTE_CODE = os.environ.get("LOCAL_RERANK_TRUST_REMOTE_CODE", "1").lower() in {"1", "true", "yes", "on"}


class RerankRequest(BaseModel):
    model: str | None = Field(default=None)
    query: str
    documents: list[str]


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "local"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelCard]


@dataclass
class RerankEngine:
    model_name: str
    tokenizer: Any
    model: Any
    device: str
    batch_size: int
    max_length: int

    @classmethod
    def load(
        cls,
        model_name: str,
        *,
        device: str = DEFAULT_DEVICE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_length: int = DEFAULT_MAX_LENGTH,
        revision: str | None = DEFAULT_MODEL_REVISION,
    ) -> "RerankEngine":
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
        model = AutoModelForSequenceClassification.from_pretrained(model_name, **model_kwargs)
        model.to(resolved_device)
        model.eval()
        return cls(
            model_name=model_name,
            tokenizer=tokenizer,
            model=model,
            device=resolved_device,
            batch_size=max(batch_size, 1),
            max_length=max(max_length, 64),
        )

    @torch.inference_mode()
    def rerank(self, query: str, documents: list[str]) -> list[dict[str, float | int]]:
        if not documents:
            return []

        scored: list[tuple[int, float]] = []
        for start in range(0, len(documents), self.batch_size):
            batch_docs = documents[start : start + self.batch_size]
            encoded = self.tokenizer(
                [query] * len(batch_docs),
                batch_docs,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            logits = self.model(**encoded).logits
            if logits.ndim == 2 and logits.shape[-1] == 1:
                logits = logits[:, 0]
            logits = logits.float().detach().cpu().tolist()
            for offset, logit in enumerate(logits):
                score = 1.0 / (1.0 + math.exp(-float(logit)))
                scored.append((start + offset, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            {"index": index, "relevance_score": score}
            for index, score in scored
        ]


app = FastAPI(title="Local Rerank Service", version="0.1.0")
ENGINE = RerankEngine.load(DEFAULT_MODEL)


def _check_api_key(authorization: str | None) -> None:
    if not DEFAULT_API_KEY:
        return
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {DEFAULT_API_KEY}"
    if authorization.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "model": ENGINE.model_name, "device": ENGINE.device}


@app.get("/v1/models", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    return ModelsResponse(data=[ModelCard(id=ENGINE.model_name)])


@app.post("/v1/rerank")
def rerank(request: RerankRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_api_key(authorization)
    requested_model = request.model or ENGINE.model_name
    if requested_model != ENGINE.model_name:
        raise HTTPException(
            status_code=400,
            detail=f"Loaded model is {ENGINE.model_name}, request asked for {requested_model}",
        )
    return {
        "model": ENGINE.model_name,
        "results": ENGINE.rerank(request.query, request.documents),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("LOCAL_RERANK_HOST", "127.0.0.1"),
        port=int(os.environ.get("LOCAL_RERANK_PORT", "8765")),
    )
