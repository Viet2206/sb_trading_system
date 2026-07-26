from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sb_system.ai_research import SBResearchAgent
from sb_system.research import ResearchLibrary, ResearchSettings


class _FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _FakeReader:
    def __init__(self, _path: str) -> None:
        self.pages = [
            _FakePage(
                "First Green Day follows a dump sequence. Mark the low of day and "
                "wait for a confirmed buy setup in the session."
            ),
            _FakePage(
                "Inside Day traders can be trapped by a false break before reversal."
            ),
        ]


class _FakeResponses:
    def create(self, **_kwargs):
        return type("Response", (), {"output_text": "Evidence supports the setup [S1]."})()


class _FakeOpenAI:
    def __init__(self, *_args, **_kwargs) -> None:
        self.responses = _FakeResponses()


class ResearchLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        docs = root / "docs" / "strategy_note"
        docs.mkdir(parents=True)
        (docs / "FirstGreenDayExamples.pdf").write_bytes(b"%PDF-fake")
        self.settings = ResearchSettings(
            docs_dir=root / "docs",
            index_path=root / "data" / "research.sqlite3",
            page_cache_dir=root / "data" / "pages",
            embedding_provider="local",
            embedding_model="text-embedding-3-small",
        )
        self.library = ResearchLibrary(self.settings)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @patch("pypdf.PdfReader", _FakeReader)
    def test_index_and_search_preserve_document_and_page_citations(self) -> None:
        indexed = self.library.index_documents()

        self.assertTrue(indexed["ready"])
        self.assertEqual(indexed["documents"], 1)
        self.assertEqual(indexed["pages"], 2)
        self.assertGreaterEqual(indexed["chunks"], 2)

        search = self.library.search("FGD dump day buy setup", limit=5)

        self.assertGreater(search["count"], 0)
        first = search["results"][0]
        self.assertEqual(first["page"], 1)
        self.assertEqual(first["citation"], "S1")
        self.assertIn("first-green-day", first["setup_types"])
        self.assertTrue(self.library.document_path(first["document_id"]).is_file())

    @patch("pypdf.PdfReader", _FakeReader)
    def test_setup_filter_and_incremental_index(self) -> None:
        first = self.library.index_documents()
        second = self.library.index_documents()
        search = self.library.search(
            "false break reversal", setup="inside-day", limit=5
        )

        self.assertEqual(first["indexed"], 1)
        self.assertEqual(second["skipped"], 1)
        self.assertGreater(search["count"], 0)
        self.assertTrue(
            all("inside-day" in item["setup_types"] for item in search["results"])
        )

    @patch("pypdf.PdfReader", _FakeReader)
    def test_agent_has_evidence_only_fallback_without_api_key(self) -> None:
        self.library.index_documents()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            result = SBResearchAgent(self.library).analyze(
                question="What supports a First Green Day?",
                symbol="XAUUSD",
                timeframe="M15",
                market_context={
                    "signal_days": ["FGD"],
                    "candidate_direction": "Buy",
                },
            )

        self.assertEqual(result["mode"], "retrieval")
        self.assertIn("[S1]", result["answer"])
        self.assertGreater(len(result["sources"]), 0)
        self.assertEqual(result["tools"][0]["name"], "search_sb_library")

    @patch("pypdf.PdfReader", _FakeReader)
    @patch("openai.OpenAI", _FakeOpenAI)
    def test_agent_synthesizes_only_after_retrieval_when_configured(self) -> None:
        self.library.index_documents()
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"},
            clear=False,
        ):
            result = SBResearchAgent(self.library).analyze(
                question="What supports a First Green Day?"
            )

        self.assertEqual(result["mode"], "ai")
        self.assertEqual(result["model"], "test-model")
        self.assertIn("[S1]", result["answer"])
        self.assertEqual(
            [tool["name"] for tool in result["tools"]],
            ["search_sb_library", "synthesize_evidence"],
        )


if __name__ == "__main__":
    unittest.main()
