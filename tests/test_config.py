from src.config import (
    LEVELS,
    MODES,
    SUBJECTS,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)


def test_expected_levels():
    assert LEVELS == ["SD", "SMP", "SMA"]


def test_expected_modes():
    assert "Jawab Cepat" in MODES
    assert "Ajari Saya Dulu" in MODES
    assert "Jelaskan ke Anak" in MODES
    assert "Bikin Latihan" in MODES


def test_expected_subjects():
    expected = {
        "Matematika",
        "IPA",
        "Fisika",
        "Kimia",
        "Biologi",
        "General",
    }
    assert set(SUBJECTS) == expected


def test_rag_tuning_is_reasonable():
    assert 1 <= RAG_TOP_K <= 3
    assert 0.0 < RAG_MIN_SCORE < 1.0
