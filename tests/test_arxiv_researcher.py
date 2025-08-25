"""
Tests for the ArxivResearcher agent.
"""

import pytest
from unittest.mock import MagicMock, patch
from synergesis.agents.arxiv_researcher import ArXivResearcher

@pytest.fixture
def researcher():
    """Returns an ArxivResearcher instance with a mock context."""
    mock_context = MagicMock()
    mock_context.shared_state = {}
    return ArXivResearcher(mock_context)

def test_summarize_paper_success(researcher, mocker):
    """
    Tests the full summarization pipeline with mocked external services.
    """
    # 1. Mock the external dependencies
    mock_pdf_content = b"This is a mock PDF content."
    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.return_value.content = mock_pdf_content
    mock_requests_get.return_value.raise_for_status.return_value = None

    mock_pdf_reader = mocker.patch("PyPDF2.PdfReader")
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "This is the extracted text from the PDF."
    mock_pdf_reader.return_value.pages = [mock_page]

    mock_litellm_completion = mocker.patch("litellm.completion")
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "This is a mock summary."
    mock_litellm_completion.return_value = mock_completion

    # 2. Call the method to be tested
    arxiv_id = "1234.5678"
    result = researcher.summarize_paper(arxiv_id)

    # 3. Assert the results
    assert result is not None
    assert result["arxiv_id"] == arxiv_id
    assert result["summary"] == "This is a mock summary."

    # 4. Assert that the external services were called correctly
    mock_requests_get.assert_called_once_with(f"https://arxiv.org/pdf/{arxiv_id}.pdf", timeout=30)
    mock_pdf_reader.assert_called_once()
    mock_litellm_completion.assert_called_once()

def test_summarize_paper_download_fails(researcher, mocker):
    """
    Tests that the summarization fails gracefully if the PDF download fails.
    """
    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.side_effect = Exception("Download failed")

    arxiv_id = "1234.5678"
    result = researcher.summarize_paper(arxiv_id)

    assert result is None

def test_summarize_paper_extraction_fails(researcher, mocker):
    """
    Tests that the summarization fails gracefully if text extraction fails.
    """
    mock_pdf_content = b"This is a mock PDF content."
    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.return_value.content = mock_pdf_content
    mock_requests_get.return_value.raise_for_status.return_value = None

    mocker.patch("PyPDF2.PdfReader", side_effect=Exception("Extraction failed"))

    arxiv_id = "1234.5678"
    result = researcher.summarize_paper(arxiv_id)

    assert result is not None
    assert result["summary"] == "Failed to extract text from PDF."
