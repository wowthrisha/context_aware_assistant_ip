import chromadb
from sentence_transformers import SentenceTransformer
from .config import *

class MemoryManager:
    def __init__(self):
        # persistent storage
        self.client = chromadb.PersistentClient(path=DB_PATH)

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME
        )

        self.embedder = SentenceTransformer(EMBEDDING_MODEL)

    def _embed(self, text):
        return self.embedder.encode(text).tolist()

    def add_memory(self, text, memory_type, memory_id):
        """
        Stores structured memory with metadata.
        Prevents duplicate storage.
        """

        embedding = self._embed(text)

        # avoid duplicates
        existing = self.collection.query(
            query_embeddings=[embedding],
            n_results=1
        )

        if existing["documents"] and text in existing["documents"][0]:
            return False

        self.collection.add(
            documents=[text],
            embeddings=[embedding],
            ids=[memory_id],
            metadatas=[{"type": memory_type}]
        )
        return True

    def retrieve_memory(self, query, memory_type=None):
        """
        Retrieves relevant memory using semantic similarity
        + metadata filtering.
        """

        query_embedding = self._embed(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=SIMILARITY_RESULTS,
            where={"type": memory_type} if memory_type else None
        )

        return results["documents"]