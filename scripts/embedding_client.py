"""
embedding_client.py

A minimal client for the Ollama embeddings API.
"""

import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5  # seconds


def get_embedding(text: str, model: str) -> list[float] | None:
    """
    Request an embedding vector for the given text from the local Ollama
    embeddings endpoint (http://localhost:11434/api/embeddings).

    Args:
        text:  The input text to embed.
        model: The name of the model to use (e.g. "nomic-embed-text").

    Returns:
        A list of floats representing the embedding vector on success,
        or None on any failure (network error, timeout, non-2xx response,
        malformed JSON, missing/unexpected payload, etc.).
    """
    url = "http://localhost:11434/api/embeddings"
    payload = {"model": model, "prompt": text}

    try:
        response = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        logger.warning("Embedding request timed out after %ss", DEFAULT_TIMEOUT)
        return None
    except requests.exceptions.ConnectionError as e:
        logger.warning("Embedding request connection error: %s", e)
        return None
    except requests.exceptions.HTTPError as e:
        logger.warning("Embedding request HTTP error: %s", e)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("Embedding request failed: %s", e)
        return None
    except ValueError as e:
        # JSON decoding errors
        logger.warning("Embedding response was not valid JSON: %s", e)
        return None
    except Exception as e:
        # Catch-all so this function never raises.
        logger.exception("Unexpected error while fetching embedding: %s", e)
        return None

    try:
        embedding = data.get("embedding")
        if embedding is None:
            return None
        # Validate it's a list of floats; coerce numeric values defensively.
        return [float(x) for x in embedding]
    except (TypeError, ValueError) as e:
        logger.warning("Embedding payload had unexpected structure: %s", e)
        return None
    except Exception as e:
        logger.exception("Unexpected error parsing embedding payload: %s", e)
        return None
