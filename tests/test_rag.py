from src.rag import RAGRetriever


def test_knowledge_base_loaded():
    rag = RAGRetriever(client=None)

    assert len(rag.chunks) == 15


def test_all_subjects_exist():
    rag = RAGRetriever(client=None)

    subjects = {chunk.subject for chunk in rag.chunks}

    assert "Matematika" in subjects
    assert "IPA" in subjects
    assert "Fisika" in subjects
    assert "Kimia" in subjects
    assert "Biologi" in subjects


def test_expected_math_chunk_exists():
    rag = RAGRetriever(client=None)

    titles = {chunk.title for chunk in rag.chunks}

    assert "Pecahan dan Pembagian Pecahan" in titles
    assert "Persamaan Linear Satu Variabel" in titles


def test_expected_science_chunk_exists():
    rag = RAGRetriever(client=None)

    titles = {chunk.title for chunk in rag.chunks}

    assert "Mengapa Langit Terlihat Biru" in titles
    assert "Fotosintesis" in titles
    assert "Mitosis dan Meiosis" in titles
    assert "Kelajuan dan Kecepatan" in titles


def test_cosine_similarity_identical_vectors():
    score = RAGRetriever._cosine_similarity(
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0],
    )

    assert abs(score - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors():
    score = RAGRetriever._cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    )

    assert abs(score) < 1e-9
