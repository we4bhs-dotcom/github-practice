import chromadb
from embedder import SentenceTransformerEmbedder
import hashlib

class NarrativeDB:
    def __init__(self, storage_path="./narrative_db"):
        print("[NarrativeDB] ChromaDB 클라이언트 초기화 시작...")
        self.client = chromadb.PersistentClient(path=storage_path)
        print("[NarrativeDB] 컬렉션 로드 중...")
        self.world = self.client.get_or_create_collection("world")
        self.embedder = SentenceTransformerEmbedder()
        self.characters = {}
        self.aliases = {}  # 캐릭터별 호칭 저장
        print("[NarrativeDB] 초기화 완료!")

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
        if results and results.get("documents") and results["documents"]:
            return results["documents"][0]
        return []

    def add_character(self, name, aliases: list = None):
        if name in self.characters:
            return
        safe_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:12]
        self.characters[name] = {
            "p": self.client.get_or_create_collection(f"char_{safe_hash}_p"),
            "b": self.client.get_or_create_collection(f"char_{safe_hash}_b"),
            "k": self.client.get_or_create_collection(f"char_{safe_hash}_k"),
            "d": self.client.get_or_create_collection(f"char_{safe_hash}_d"),
        }
        self.aliases[name] = aliases if aliases else []

    def update_aliases(self, name, aliases: list):
        if name in self.characters:
            self.aliases[name] = aliases

    def get_aliases(self, name) -> list:
        return self.aliases.get(name, [])