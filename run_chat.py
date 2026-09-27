def print_rag_trace(bot: BapakBelajarLagiBot):
    if bot.last_rag_error:
        print(
            "\n[RAG] Retrieval tidak tersedia "
            f"pada turn ini: {bot.last_rag_error}"
        )
        return

    if not bot.last_rag_results:
        print(
            "\n[RAG] Tidak ada materi yang melewati "
            "relevance threshold."
        )
        return

    print("\n[RAG] Materi terambil:")

    for i, result in enumerate(
        bot.last_rag_results,
        start=1,
    ):
        print(
            f"  {i}. {result.subject} > "
            f"{result.title} "
            f"| score={result.score:.3f} "
            f"| {result.source}"
        )