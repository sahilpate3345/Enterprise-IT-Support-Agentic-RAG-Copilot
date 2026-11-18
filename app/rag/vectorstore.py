from typing import Iterable, List, Optional
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.services.embeddings import get_embeddings_model

_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = get_embeddings_model()
    return _embeddings


def get_client() -> Optional[QdrantClient]:
    settings = get_settings()
    if not settings.qdrant_url or not settings.qdrant_api_key:
        return None
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=30,
    )


def vector_store_exists() -> bool:
    settings = get_settings()
    client = get_client()
    if not client:
        return False
    try:
        return client.collection_exists(settings.qdrant_collection_name)
    except Exception:
        return False


def build_vector_store(chunks: List[Document]) -> QdrantVectorStore:
    if not chunks:
        raise ValueError("Chunks cannot be empty.")

    settings = get_settings()
    embeddings_model = get_embeddings()

    if settings.qdrant_url and settings.qdrant_api_key:
        try:
            return QdrantVectorStore.from_documents(
                documents=chunks,
                embedding=embeddings_model,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                collection_name=settings.qdrant_collection_name,
            )
        except Exception as e:
            print(f"Qdrant Cloud error: {e}")
            print("Falling back to in-memory Qdrant.")

    return QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings_model,
        location=":memory:",
        collection_name=settings.qdrant_collection_name,
    )


def load_vector_store() -> Optional[QdrantVectorStore]:
    settings = get_settings()
    if not settings.qdrant_url or not settings.qdrant_api_key:
        return None

    try:
        return QdrantVectorStore.from_existing_collection(
            embedding=get_embeddings(),
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection_name,
        )
    except Exception as e:
        print(f"Failed to load Qdrant collection: {e}")
        return None


def add_documents(documents: Iterable[Document]) -> List[str]:
    docs_list = list(documents)
    if not docs_list:
        return []

    settings = get_settings()
    store = load_vector_store()

    if store is None:
        store = build_vector_store(docs_list)
        # from_documents has already inserted the documents
        return [str(i) for i in range(len(docs_list))]

    return store.add_documents(docs_list)


def get_retriever(vector_store: Optional[QdrantVectorStore] = None, k: Optional[int] = None):
    if vector_store is None:
        vector_store = load_vector_store()

    if vector_store is None:
        raise ValueError("Vector store is not initialized or collection does not exist.")

    settings = get_settings()
    if k is None:
        k = settings.top_k

    return vector_store.as_retriever(search_kwargs={"k": k})
