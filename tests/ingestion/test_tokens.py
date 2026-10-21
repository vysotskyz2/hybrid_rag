from docs_rag.ingestion.tokens import RegexTokenCounter


def test_regex_token_counter_counts_words_and_punctuation() -> None:
    counter = RegexTokenCounter()

    assert counter.count("Hello, world!") == 4
    assert counter.count("") == 0
    assert counter.count("Привет, мир!") == 4


def test_regex_token_counter_handles_identifiers() -> None:
    counter = RegexTokenCounter()

    assert counter.count("HTTPException") == 1
    assert counter.count("background_tasks") == 1
