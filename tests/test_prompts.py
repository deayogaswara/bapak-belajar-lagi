from src.prompts import build_system_instruction


def test_prompt_contains_context():
    prompt = build_system_instruction(
        level="SD",
        subject="IPA",
        mode="Jelaskan ke Anak",
    )

    assert "Jenjang anak: SD" in prompt
    assert "Mata pelajaran pilihan: IPA" in prompt
    assert "Mode jawaban: Jelaskan ke Anak" in prompt


def test_prompt_contains_science_guardrail():
    prompt = build_system_instruction(
        level="SD",
        subject="IPA",
        mode="Jelaskan ke Anak",
    )

    assert "mekanisme inti yang benar" in prompt
    assert "personifikasi" in prompt


def test_prompt_contains_physics_speed_guardrail():
    prompt = build_system_instruction(
        level="SMP",
        subject="Fisika",
        mode="Ajari Saya Dulu",
    )

    assert "kelajuan rata-rata" in prompt
    assert "kecepatan rata-rata" in prompt


def test_prompt_contains_rag_rule():
    prompt = build_system_instruction(
        level="SMA",
        subject="Biologi",
        mode="Jawab Cepat",
    )

    assert "ATURAN RAG / MATERI REFERENSI" in prompt
