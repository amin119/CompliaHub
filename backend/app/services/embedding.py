from typing import Literal

import voyageai

from app.core.config import get_settings

# voyage-law-2's output dimensionality — fixed for the model, not something
# the API returns per-call. Used by vector_store.py to size the Qdrant
# collection. If voyage_model in Settings ever changes, this must change too.
EMBEDDING_DIM = 1024

# Voyage caps each embed() call at 128 texts — batching here keeps a
# large document's chunk count from ever hitting that limit in one call.
_BATCH_SIZE = 128


def embed_texts(texts: list[str], input_type: Literal["document", "query"]) -> list[list[float]]:
    """Embed a list of texts with Voyage. `input_type` matters: Voyage's
    embed models are trained with distinct prompts for indexed documents vs.
    search queries, so passing the wrong one measurably hurts retrieval
    quality even though both return same-shaped vectors.
    """
    if not texts:
        return []

    settings = get_settings()
    client = voyageai.Client(api_key=settings.voyage_api_key)

    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        result = client.embed(batch, model=settings.voyage_model, input_type=input_type)
        vectors.extend(result.embeddings)
    return vectors
