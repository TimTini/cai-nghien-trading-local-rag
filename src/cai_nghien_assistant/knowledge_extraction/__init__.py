"""Deterministic knowledge extraction from transcripts and OCR — no chat."""

from .batch import run_extract_batch
from .schema import KnowledgeFact

__all__ = ["KnowledgeFact", "run_extract_batch"]
