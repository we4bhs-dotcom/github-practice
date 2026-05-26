import chromadb
from embedder import SentenceTransformerEmbedder

class NarrativeDB:
    def __init__(self):
        self.client = chromadb.Client()
        self.world = self.client.get_or_create_collection("world")
        self.embedder = SentenceTransformerEmbedder()

    def add(self, collection, text, doc_id):
        vector = self.embedder.embed(text)
        collection.add(
            documents=[text],
            embeddings=[vector],
            ids=[doc_id]
        )

    def search(self, collection, query, top_k=3):
        vector = self.embedder.embed(query)
        results = collection.query(
            query_embeddings=[vector],
            n_results=top_k
        )
        return results["documents"][0]
    def add_character(self, name):
        self.characters[name] = {
        "p": self.client.get_or_create_collection(f"char_{name}_p"),
        "b": self.client.get_or_create_collection(f"char_{name}_b"),
        "k": self.client.get_or_create_collection(f"char_{name}_k"),
        "d": self.client.get_or_create_collection(f"char_{name}_d"),
    }