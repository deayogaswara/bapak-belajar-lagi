from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_FILES = {
    ".env",
    ".streamlit/secrets.toml",
}

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".toml", ".json",
    ".yaml", ".yml", ".ini", ".cfg", ".env",
}

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(
        r"GEMINI_API_KEY\s*=\s*(?!your_gemini_api_key_here)"
        r"[^\s#]+"
    ),
]


def iter_text_files():
    ignored_parts = {
        ".venv",
        "venv",
        ".git",
        "__pycache__",
        ".rag_cache",
        ".pytest_cache",
    }

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(part in ignored_parts for part in path.parts):
            continue

        if (
            path.suffix.lower() in TEXT_EXTENSIONS
            or path.name == ".env.example"
        ):
            yield path


def main():
    problems = []

    for forbidden in FORBIDDEN_FILES:
        path = ROOT / forbidden
        if path.exists():
            problems.append(
                f"Sensitive local file exists: {forbidden}"
            )

    for path in iter_text_files():
        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue

        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                problems.append(
                    f"Possible secret in: "
                    f"{path.relative_to(ROOT)}"
                )
                break

    if problems:
        print("PRE-FLIGHT FAILED")
        for item in problems:
            print(f"- {item}")
        sys.exit(1)

    print("PRE-FLIGHT PASS")
    print("- No obvious Gemini API key found in source files.")
    print("- No Streamlit secrets.toml found.")
    print("- Repository is ready for manual Git review.")


if __name__ == "__main__":
    main()
