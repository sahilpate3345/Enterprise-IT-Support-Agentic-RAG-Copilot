from langchain_community.embeddings import JinaEmbeddings
from app.core.config import get_settings

_embeddings = None


def get_embeddings_model() -> JinaEmbeddings:
    global _embeddings

    if _embeddings is None:
        settings = get_settings()
        _embeddings = JinaEmbeddings(
            jina_api_key=settings.jina_api_key,
            model_name=settings.model_name
        )

    return _embeddings
