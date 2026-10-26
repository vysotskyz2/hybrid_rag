import logging

import structlog


def configure_logging(level: str = "INFO", log_format: str = "json") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format="%(message)s")
    for noisy_logger in (
        "httpx",
        "httpcore",
        "huggingface_hub",
        "sentence_transformers",
        "urllib3",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    renderer = (
        structlog.processors.JSONRenderer()
        if log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
