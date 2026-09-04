"""Unit tests for the Ollama embedding client."""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import embedding_client


class GetEmbeddingTests(unittest.TestCase):
    """Tests for the get_embedding function."""

    def test_successful_embedding_returns_floats(self) -> None:
        response = mock.Mock()
        response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        response.raise_for_status.return_value = None

        with mock.patch.object(embedding_client.requests, "post", return_value=response) as post:
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertEqual(result, [0.1, 0.2, 0.3])
        post.assert_called_once()
        call_kwargs = post.call_args.kwargs
        self.assertEqual(call_kwargs["json"], {"model": "nomic-embed-text", "prompt": "hello"})
        self.assertEqual(call_kwargs["timeout"], embedding_client.DEFAULT_TIMEOUT)
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/embeddings")

    def test_timeout_returns_none_and_does_not_raise(self) -> None:
        with mock.patch.object(
            embedding_client.requests,
            "post",
            side_effect=embedding_client.requests.exceptions.Timeout("timed out"),
        ):
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertIsNone(result)

    def test_connection_error_returns_none_and_does_not_raise(self) -> None:
        with mock.patch.object(
            embedding_client.requests,
            "post",
            side_effect=embedding_client.requests.exceptions.ConnectionError("refused"),
        ):
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertIsNone(result)

    def test_http_error_returns_none(self) -> None:
        response = mock.Mock()
        response.raise_for_status.side_effect = (
            embedding_client.requests.exceptions.HTTPError("500 server error")
        )

        with mock.patch.object(embedding_client.requests, "post", return_value=response):
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertIsNone(result)

    def test_invalid_json_returns_none(self) -> None:
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("not json")

        with mock.patch.object(embedding_client.requests, "post", return_value=response):
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertIsNone(result)

    def test_missing_embedding_key_returns_none(self) -> None:
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"no_embedding_here": True}

        with mock.patch.object(embedding_client.requests, "post", return_value=response):
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertIsNone(result)

    def test_unexpected_payload_returns_none(self) -> None:
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"embedding": "not a list"}

        with mock.patch.object(embedding_client.requests, "post", return_value=response):
            result = embedding_client.get_embedding("hello", "nomic-embed-text")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
