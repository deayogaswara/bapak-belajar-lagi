import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src.config import (
    FALLBACK_MODEL,
    LEVELS,
    MODES,
    PRIMARY_MODEL,
    SUBJECTS,
)
from src.prompts import build_system_instruction
from src.rag import RAGRetriever, RetrievalResult
from src.tools import (
    calculate,
    clear_tool_call_log,
    get_tool_call_log,
)


RETRYABLE_MODEL_CODES = {429, 503}

FOLLOW_UP_MARKERS = (
    "yang tadi",
    "tadi",
    "itu",
    "tersebut",
    "dia",
    "mereka",
    "jelaskan lagi",
    "jelasin lagi",
    "lebih gampang",
    "lebih sederhana",
    "kenapa begitu",
    "mengapa begitu",
    "kalau ",
    "bagaimana kalau",
    "terus ",
    "lalu ",
)


class BapakBelajarLagiBot:
    def __init__(
        self,
        level: str = "SD",
        subject: str = "General",
        mode: str = "Ajari Saya Dulu",
    ):
        load_dotenv()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY belum ditemukan. "
                "Pastikan file .env tersedia."
            )

        self.client = genai.Client(api_key=api_key)

        self.level = level
        self.subject = subject
        self.mode = mode

        self.last_tool_calls: list[dict[str, str]] = []
        self.last_rag_results: list[RetrievalResult] = []
        self.last_rag_error: str | None = None
        self.last_model_error: str | None = None

        # Menyimpan pertanyaan mentah user agar retrieval RAG
        # dapat memahami follow-up seperti "yang tadi" / "dia".
        self.recent_user_questions: list[str] = []

        self._validate_context()

        self.rag = RAGRetriever(self.client)

        self.active_model = PRIMARY_MODEL
        self.chat = self._create_chat(
            model=PRIMARY_MODEL,
            history=[],
        )

    @staticmethod
    def _validate_choice(
        value: str,
        allowed: list[str],
        label: str,
    ):
        if value not in allowed:
            raise ValueError(
                f"{label} tidak valid: {value}. "
                f"Pilihan: {', '.join(allowed)}"
            )

    def _validate_context(self):
        self._validate_choice(self.level, LEVELS, "Jenjang")
        self._validate_choice(
            self.subject,
            SUBJECTS,
            "Mata pelajaran",
        )
        self._validate_choice(self.mode, MODES, "Mode")

    def _build_config(self) -> types.GenerateContentConfig:
        system_instruction = build_system_instruction(
            level=self.level,
            subject=self.subject,
            mode=self.mode,
        )

        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(
                thinking_level="low"
            ),
            max_output_tokens=1200,
            tools=[calculate],
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=2
                )
            ),
        )

    def _create_chat(
        self,
        model: str,
        history: list,
    ):
        return self.client.chats.create(
            model=model,
            config=self._build_config(),
            history=history,
        )

    def _current_history(self) -> list:
        return list(
            self.chat.get_history(curated=True)
        )

    @staticmethod
    def _api_error_code(exc: Exception) -> int | None:
        code = getattr(exc, "code", None)

        if isinstance(code, int):
            return code

        try:
            return int(code)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_retryable_model_error(
        cls,
        exc: Exception,
    ) -> bool:
        return (
            cls._api_error_code(exc)
            in RETRYABLE_MODEL_CODES
        )

    @classmethod
    def _friendly_model_error(
        cls,
        exc: Exception,
    ) -> str:
        code = cls._api_error_code(exc)

        if code == 429:
            return (
                "Kuota atau rate limit Gemini untuk model "
                "yang tersedia sedang tercapai. "
                "Coba lagi setelah kuota tersedia kembali "
                "atau gunakan project dengan billing aktif."
            )

        if code == 503:
            return (
                "Model Gemini sedang mengalami beban tinggi. "
                "Silakan coba lagi beberapa saat."
            )

        return "Layanan Gemini sedang mengalami kendala."

    def _needs_contextual_retrieval(
        self,
        question: str,
    ) -> bool:
        if not self.recent_user_questions:
            return False

        normalized = question.lower().strip()

        return any(
            marker in normalized
            for marker in FOLLOW_UP_MARKERS
        )

    def _build_retrieval_query(
        self,
        question: str,
    ) -> str:
        if not self._needs_contextual_retrieval(question):
            return question

        previous = self.recent_user_questions[-1]

        return (
            f"Pertanyaan sebelumnya: {previous}\n"
            f"Pertanyaan lanjutan: {question}"
        )

    def _retrieve_context(
        self,
        question: str,
    ) -> str:
        self.last_rag_results = []
        self.last_rag_error = None

        retrieval_query = self._build_retrieval_query(
            question
        )

        try:
            results = self.rag.retrieve(
                question=retrieval_query,
                subject=self.subject,
            )
        except Exception as exc:
            self.last_rag_error = str(exc)
            return ""

        self.last_rag_results = results
        return self.rag.build_context(results)

    @staticmethod
    def _augment_question(
        question: str,
        rag_context: str,
    ) -> str:
        if not rag_context:
            return question

        return (
            "PERTANYAAN PENGGUNA:\n"
            f"{question}\n\n"
            "KONTEKS MATERI TERAMBIL:\n"
            f"{rag_context}\n\n"
            "INSTRUKSI:\n"
            "Jawab pertanyaan pengguna secara natural. "
            "Gunakan materi terambil jika relevan, "
            "tanpa membahas proses retrieval."
        )

    def _send_with_fallback(
        self,
        augmented_question: str,
        history_before_turn: list,
    ):
        try:
            return self.chat.send_message(
                augmented_question
            )

        except errors.APIError as exc:
            self.last_model_error = str(exc)

            if not self._is_retryable_model_error(exc):
                raise

            if self.active_model == FALLBACK_MODEL:
                raise RuntimeError(
                    self._friendly_model_error(exc)
                ) from exc

            error_code = self._api_error_code(exc)

            print(
                f"\n{PRIMARY_MODEL} tidak tersedia "
                f"(HTTP {error_code})."
                f"\nMencoba model cadangan: "
                f"{FALLBACK_MODEL}..."
            )

            self.active_model = FALLBACK_MODEL
            self.chat = self._create_chat(
                model=FALLBACK_MODEL,
                history=history_before_turn,
            )

            clear_tool_call_log()

            try:
                response = self.chat.send_message(
                    augmented_question
                )
                self.last_model_error = None
                return response

            except errors.APIError as fallback_exc:
                self.last_model_error = str(
                    fallback_exc
                )

                if self._is_retryable_model_error(
                    fallback_exc
                ):
                    raise RuntimeError(
                        self._friendly_model_error(
                            fallback_exc
                        )
                    ) from fallback_exc

                raise

    def ask(self, question: str) -> str:
        question = question.strip()

        if not question:
            raise ValueError(
                "Pertanyaan tidak boleh kosong."
            )

        self.last_model_error = None

        history_before_turn = self._current_history()

        rag_context = self._retrieve_context(question)
        augmented_question = self._augment_question(
            question,
            rag_context,
        )

        clear_tool_call_log()
        self.last_tool_calls = []

        response = self._send_with_fallback(
            augmented_question=augmented_question,
            history_before_turn=history_before_turn,
        )

        if not response.text:
            raise RuntimeError(
                "Gemini tidak mengembalikan jawaban teks."
            )

        self.last_tool_calls = get_tool_call_log()

        # Simpan raw question hanya setelah turn berhasil.
        self.recent_user_questions.append(question)
        self.recent_user_questions = (
            self.recent_user_questions[-5:]
        )

        return response.text.strip()

    def reset(self):
        self.active_model = PRIMARY_MODEL
        self.last_tool_calls = []
        self.last_rag_results = []
        self.last_rag_error = None
        self.last_model_error = None
        self.recent_user_questions = []
        clear_tool_call_log()

        self.chat = self._create_chat(
            model=PRIMARY_MODEL,
            history=[],
        )

    def change_context(
        self,
        level: str,
        subject: str,
        mode: str,
    ):
        self.level = level
        self.subject = subject
        self.mode = mode

        self._validate_context()
        self.reset()

    @property
    def turn_count(self) -> int:
        return sum(
            1
            for item in self._current_history()
            if getattr(item, "role", None) == "user"
        )
