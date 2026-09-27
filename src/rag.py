import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from google.genai import types

from src.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
CACHE_DIR = PROJECT_ROOT / ".rag_cache"
CACHE_FILE = CACHE_DIR / "embeddings.json"


SUBJECT_SCOPE = {
    "Matematika": {"Matematika"},
    "IPA": {"IPA", "Fisika", "Kimia", "Biologi"},
    "Fisika": {"Fisika", "IPA"},
    "Kimia": {"Kimia", "IPA"},
    "Biologi": {"Biologi", "IPA"},
    "General": {
        "Matematika",
        "IPA",
        "Fisika",
        "Kimia",
        "Biologi",
    },
}


@dataclass
class KnowledgeChunk:
    chunk_id: str
    subject: str
    title: str
    text: str
    source: str
    embedding: list[float] | None = None


@dataclass
class RetrievalResult:
    chunk_id: str
    subject: str
    title: str
    text: str
    source: str
    score: float


class RAGRetriever:
    def __init__(self, client):
        self.client = client
        self.chunks = self._load_chunks()
        self.index_ready = False

    @staticmethod
    def _subject_from_path(path: Path) -> str:
        mapping = {
            "matematika": "Matematika",
            "ipa": "IPA",
            "fisika": "Fisika",
            "kimia": "Kimia",
            "biologi": "Biologi",
        }
        return mapping.get(path.stem.lower(), path.stem.title())

    def _load_chunks(self) -> list[KnowledgeChunk]:
        if not KNOWLEDGE_DIR.exists():
            raise RuntimeError(
                f"Folder knowledge tidak ditemukan: {KNOWLEDGE_DIR}"
            )

        chunks: list[KnowledgeChunk] = []

        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            subject = self._subject_from_path(path)
            raw = path.read_text(encoding="utf-8")
            lines = raw.splitlines()

            current_title = None
            current_lines: list[str] = []
            section_number = 0

            def flush():
                nonlocal current_title
                nonlocal current_lines
                nonlocal section_number

                if not current_title:
                    return

                text = "\n".join(current_lines).strip()
                if not text:
                    return

                section_number += 1
                chunk_id = (
                    f"{path.stem}-{section_number:02d}"
                )

                chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        subject=subject,
                        title=current_title,
                        text=text,
                        source=path.name,
                    )
                )

            for line in lines:
                if line.startswith("## "):
                    flush()
                    current_title = line[3:].strip()
                    current_lines = []
                elif current_title is not None:
                    current_lines.append(line)

            flush()

        if not chunks:
            raise RuntimeError(
                "Knowledge base kosong. "
                "Pastikan file Markdown memiliki heading ##."
            )

        return chunks

    def _fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(EMBEDDING_MODEL.encode("utf-8"))
        digest.update(str(EMBEDDING_DIMENSION).encode("utf-8"))

        for chunk in self.chunks:
            digest.update(chunk.chunk_id.encode("utf-8"))
            digest.update(chunk.subject.encode("utf-8"))
            digest.update(chunk.title.encode("utf-8"))
            digest.update(chunk.text.encode("utf-8"))

        return digest.hexdigest()

    def _load_cache(self) -> bool:
        if not CACHE_FILE.exists():
            return False

        try:
            data = json.loads(
                CACHE_FILE.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            return False

        if data.get("fingerprint") != self._fingerprint():
            return False

        if data.get("model") != EMBEDDING_MODEL:
            return False

        if (
            data.get("dimension")
            != EMBEDDING_DIMENSION
        ):
            return False

        cached_chunks = {
            item["chunk_id"]: item
            for item in data.get("chunks", [])
        }

        for chunk in self.chunks:
            cached = cached_chunks.get(chunk.chunk_id)
            if not cached:
                return False

            embedding = cached.get("embedding")
            if not isinstance(embedding, list):
                return False

            chunk.embedding = embedding

        return True

    def _save_cache(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "fingerprint": self._fingerprint(),
            "model": EMBEDDING_MODEL,
            "dimension": EMBEDDING_DIMENSION,
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "embedding": chunk.embedding,
                }
                for chunk in self.chunks
            ],
        }

        CACHE_FILE.write_text(
            json.dumps(data),
            encoding="utf-8",
        )

    def _embed(self, text: str) -> list[float]:
        result = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSION
            ),
        )

        if not result.embeddings:
            raise RuntimeError(
                "Embedding API tidak mengembalikan embedding."
            )

        values = result.embeddings[0].values

        if not values:
            raise RuntimeError(
                "Embedding API mengembalikan vector kosong."
            )

        return [float(value) for value in values]

    @staticmethod
    def _prepare_document(
        chunk: KnowledgeChunk,
    ) -> str:
        title = f"{chunk.subject} - {chunk.title}"
        return (
            f"title: {title} | "
            f"text: {chunk.text}"
        )

    @staticmethod
    def _prepare_query(question: str) -> str:
        return (
            "task: question answering | "
            f"query: {question}"
        )

    def ensure_index(self):
        if self.index_ready:
            return

        if self._load_cache():
            self.index_ready = True
            return

        total = len(self.chunks)
        print(
            f"\n[RAG] Membangun embedding index "
            f"({total} materi)..."
        )

        for i, chunk in enumerate(
            self.chunks,
            start=1,
        ):
            chunk.embedding = self._embed(
                self._prepare_document(chunk)
            )
            print(
                f"[RAG] Indexing {i}/{total}: "
                f"{chunk.subject} > {chunk.title}"
            )

        self._save_cache()
        self.index_ready = True
        print("[RAG] Index siap dan disimpan ke cache.")

    @staticmethod
    def _cosine_similarity(
        a: list[float],
        b: list[float],
    ) -> float:
        if len(a) != len(b):
            raise ValueError(
                "Dimensi embedding tidak sama."
            )

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def retrieve(
        self,
        question: str,
        subject: str,
        top_k: int = RAG_TOP_K,
        min_score: float = RAG_MIN_SCORE,
    ) -> list[RetrievalResult]:
        self.ensure_index()

        query_embedding = self._embed(
            self._prepare_query(question)
        )

        allowed_subjects = SUBJECT_SCOPE.get(
            subject,
            SUBJECT_SCOPE["General"],
        )

        scored: list[RetrievalResult] = []

        for chunk in self.chunks:
            if chunk.subject not in allowed_subjects:
                continue

            if chunk.embedding is None:
                continue

            score = self._cosine_similarity(
                query_embedding,
                chunk.embedding,
            )

            scored.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    subject=chunk.subject,
                    title=chunk.title,
                    text=chunk.text,
                    source=chunk.source,
                    score=score,
                )
            )

        scored.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return [
            item
            for item in scored[:top_k]
            if item.score >= min_score
        ]

    @staticmethod
    def build_context(
        results: list[RetrievalResult],
    ) -> str:
        if not results:
            return ""

        blocks = []

        for i, result in enumerate(
            results,
            start=1,
        ):
            blocks.append(
                f"[Materi {i}]\n"
                f"Topik: {result.subject} - "
                f"{result.title}\n"
                f"Sumber internal: {result.source}\n"
                f"Isi:\n{result.text}"
            )

        return "\n\n".join(blocks)
