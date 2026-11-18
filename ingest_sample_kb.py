
from pathlib import Path

from app.core.config import get_settings
from app.rag.vectorstore import add_documents
from app.services.ingestion import load_file, chunk_documents

settings = get_settings()

# Get knowledge base directory
folder = Path(settings.sample_kb_dir)

# Get all files
files = [p for p in folder.iterdir() if p.is_file()]

# Load documents
all_docs = []

for file_path in files:
    all_docs.extend(load_file(file_path))

# Split documents into chunks
chunks = chunk_documents(all_docs)

# Store documents in vector database
ids = add_documents(chunks)

print(
    f"Indexed {len(files)} files -> "
    f"{len(chunks)} chunks -> {len(ids)} vectors"
)
