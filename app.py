import os

import streamlit as st

from src.chatbot import BapakBelajarLagiBot
from src.config import LEVELS, MODES, SUBJECTS


st.set_page_config(
    page_title="Bapak Belajar Lagi",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="expanded",
)


def load_api_key():
    if os.getenv("GEMINI_API_KEY"):
        return

    try:
        secret_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        secret_key = None

    if secret_key:
        os.environ["GEMINI_API_KEY"] = secret_key


def init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "bot" not in st.session_state:
        st.session_state.bot = None

    if "bot_context" not in st.session_state:
        st.session_state.bot_context = None


def build_bot(level: str, subject: str, mode: str):
    load_api_key()

    try:
        st.session_state.bot = BapakBelajarLagiBot(
            level=level,
            subject=subject,
            mode=mode,
        )
        st.session_state.bot_context = (
            level,
            subject,
            mode,
        )
    except Exception as exc:
        st.session_state.bot = None
        st.error(
            "Chatbot belum bisa dijalankan. "
            "Periksa GEMINI_API_KEY dan koneksi API."
        )
        with st.expander("Detail teknis"):
            st.code(str(exc))
        st.stop()


def reset_conversation():
    if st.session_state.bot is not None:
        st.session_state.bot.reset()

    st.session_state.messages = []


def serialize_rag_results(bot):
    return [
        {
            "subject": item.subject,
            "title": item.title,
            "score": float(item.score),
            "source": item.source,
        }
        for item in bot.last_rag_results
    ]


def build_metadata(bot):
    return {
        "model": bot.active_model,
        "tool_calls": [
            dict(item)
            for item in bot.last_tool_calls
        ],
        "rag_results": serialize_rag_results(bot),
        "rag_error": bot.last_rag_error,
        "model_error": bot.last_model_error,
    }


def render_metadata(metadata: dict):
    if not metadata:
        return

    with st.expander(
        "Lihat proses AI",
        expanded=False,
    ):
        st.caption(
            f"Model aktif: {metadata.get('model', '-')}"
        )

        model_error = metadata.get("model_error")
        if model_error:
            st.markdown("**Status Gemini API**")
            st.warning(
                "Model mengalami error pada request ini."
            )
            st.code(model_error)

        st.markdown("**RAG / materi referensi**")

        rag_results = metadata.get(
            "rag_results",
            [],
        )
        rag_error = metadata.get("rag_error")

        if rag_error:
            st.warning(
                "Retrieval materi tidak tersedia pada "
                "jawaban ini."
            )
            st.code(rag_error)

        elif rag_results:
            for i, item in enumerate(
                rag_results,
                start=1,
            ):
                st.write(
                    f"{i}. {item['subject']} > "
                    f"{item['title']} "
                    f"(score {item['score']:.3f})"
                )
                st.caption(
                    f"Sumber: {item['source']}"
                )

        else:
            st.caption(
                "Tidak ada materi yang melewati "
                "relevance threshold."
            )

        st.markdown("**Function calling**")

        tool_calls = metadata.get(
            "tool_calls",
            [],
        )

        if tool_calls:
            for call in tool_calls:
                st.code(
                    "calculate("
                    f"{call['expression']}"
                    f") -> {call['result']}"
                )
        else:
            st.caption(
                "Calculator tidak digunakan."
            )


def process_prompt(prompt: str):
    bot = st.session_state.bot

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(
            "Mencari materi dan menyusun jawaban..."
        ):
            try:
                answer = bot.ask(prompt)
                metadata = build_metadata(bot)

            except Exception as exc:
                # Jangan salah label API/model error sebagai RAG error.
                metadata = build_metadata(bot)
                metadata["model_error"] = str(exc)

                answer = (
                    "Maaf, layanan Gemini sedang mengalami "
                    "kendala atau kuota sementara tercapai. "
                    "Coba lagi beberapa saat."
                )

        st.markdown(answer)
        render_metadata(metadata)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "metadata": metadata,
        }
    )


init_state()

st.title("Bapak Belajar Lagi")
st.caption("AI Study Companion for Parents")
st.write(
    "Bantu orang tua memahami kembali pelajaran sekolah "
    "agar lebih siap mendampingi anak belajar."
)

with st.sidebar:
    st.header("Pengaturan Belajar")

    level = st.selectbox(
        "Jenjang anak",
        LEVELS,
        index=0,
    )

    subject = st.selectbox(
        "Mata pelajaran",
        SUBJECTS,
        index=0,
    )

    mode = st.selectbox(
        "Mode jawaban",
        MODES,
        index=1,
    )

    st.divider()

    st.markdown("**Mode jawaban**")
    st.caption(
        "Jawab Cepat: langsung ke inti\n\n"
        "Ajari Saya Dulu: pahami konsepnya dulu\n\n"
        "Jelaskan ke Anak: versi sederhana untuk anak\n\n"
        "Bikin Latihan: 3 soal bertahap + pembahasan"
    )

    st.divider()

    if st.button(
        "Mulai percakapan baru",
        use_container_width=True,
    ):
        reset_conversation()
        st.rerun()

current_context = (
    level,
    subject,
    mode,
)

if st.session_state.bot is None:
    build_bot(
        level=level,
        subject=subject,
        mode=mode,
    )

elif (
    st.session_state.bot_context
    != current_context
):
    st.session_state.bot.change_context(
        level=level,
        subject=subject,
        mode=mode,
    )
    st.session_state.bot_context = current_context
    st.session_state.messages = []
    st.info(
        "Pengaturan belajar berubah. "
        "Percakapan dimulai dari konteks baru."
    )

if not st.session_state.messages:
    st.info(
        "Contoh: “Kenapa 1/2 dibagi 1/4 hasilnya 2?” "
        "atau “Kenapa langit terlihat biru?”"
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant":
            render_metadata(
                message.get(
                    "metadata",
                    {},
                )
            )

prompt = st.chat_input(
    "Tulis pertanyaan tentang pelajaran anak..."
)

if prompt:
    process_prompt(prompt)
