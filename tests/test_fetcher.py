#!/usr/bin/env python3
"""
Unit tests for NC Business Document Fetcher
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nc_business_doc_fetcher import (
    BusinessRecord,
    ScraperConfiguration,
    NCBusinessDocumentFetcher,
    DocumentRetrievalError,
    SearchOperationError
)


class TestBusinessRecord(unittest.TestCase):
    """Tests for BusinessRecord dataclass."""
    
    # Sample test data - static values for test consistency
    SAMPLE_DATE = "2020-06-15"
    
    def test_creation_with_required_fields(self):
        """Verify BusinessRecord can be created with required fields."""
        record = BusinessRecord(
            entity_name="Test Company LLC",
            sos_identifier="12345678",
            status_text="Active",
            date_registered=self.SAMPLE_DATE,
            detail_link="https://example.com/detail"
        )
        
        self.assertEqual(record.entity_name, "Test Company LLC")
        self.assertEqual(record.sos_identifier, "12345678")
        self.assertEqual(record.status_text, "Active")
        self.assertEqual(record.date_registered, self.SAMPLE_DATE)
        self.assertEqual(record.pdf_documents, [])


class TestScraperConfiguration(unittest.TestCase):
    """Tests for ScraperConfiguration dataclass."""
    
    def test_default_configuration_values(self):
        """Verify default configuration values are set correctly."""
        config = ScraperConfiguration()
        
        self.assertEqual(config.target_base_url, "https://www.sosnc.gov")
        self.assertEqual(config.storage_directory, "./fetched_documents")
        self.assertEqual(config.request_delay_seconds, 1.5)
        self.assertEqual(config.connection_timeout, 30)
        self.assertEqual(config.max_retry_attempts, 3)
    
    def test_custom_configuration_values(self):
        """Verify custom configuration values are applied."""
        config = ScraperConfiguration(
            storage_directory="/custom/path",
            request_delay_seconds=3.0,
            connection_timeout=60
        )
        
        self.assertEqual(config.storage_directory, "/custom/path")
        self.assertEqual(config.request_delay_seconds, 3.0)
        self.assertEqual(config.connection_timeout, 60)


class TestNCBusinessDocumentFetcher(unittest.TestCase):
    """Tests for NCBusinessDocumentFetcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = ScraperConfiguration(
            storage_directory=self.temp_dir,
            request_delay_seconds=0.01  # Fast for testing
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_fetcher_initialization(self):
        """Verify fetcher initializes correctly."""
        fetcher = NCBusinessDocumentFetcher(self.config)
        
        self.assertIsNotNone(fetcher._http_session)
        self.assertTrue(Path(self.temp_dir).exists())
        
        fetcher.close()
    
    def test_storage_directory_creation(self):
        """Verify storage directory is created if it doesn't exist."""
        new_path = os.path.join(self.temp_dir, "new_subdir")
        config = ScraperConfiguration(
            storage_directory=new_path,
            request_delay_seconds=0.01
        )
        
        self.assertFalse(os.path.exists(new_path))
        
        fetcher = NCBusinessDocumentFetcher(config)
        
        self.assertTrue(os.path.exists(new_path))
        
        fetcher.close()
    
    @patch('nc_business_doc_fetcher.NCBusinessDocumentFetcher._perform_request')
    def test_locate_pdf_links_extraction(self, mock_request):
        """Verify PDF links are correctly extracted from HTML."""
        fetcher = NCBusinessDocumentFetcher(self.config)
        
        sample_html = """
        <html>
        <body>
            <a href="/documents/file1.pdf">Document 1</a>
            <a href="/documents/file2.PDF">Document 2</a>
            <a href="/other/page.html">Not a PDF</a>
        </body>
        </html>
        """
        
        pdf_links = fetcher._locate_pdf_links(sample_html)
        
        self.assertEqual(len(pdf_links), 2)
        self.assertTrue(all(".pdf" in link.lower() for link in pdf_links))
        
        fetcher.close()
    
    @patch('nc_business_doc_fetcher.NCBusinessDocumentFetcher._perform_request')
    def test_extract_business_records_empty_table(self, mock_request):
        """Verify empty result when no table found."""
        fetcher = NCBusinessDocumentFetcher(self.config)
        
        sample_html = "<html><body><p>No results</p></body></html>"
        
        records = fetcher._extract_business_records(sample_html)
        
        self.assertEqual(len(records), 0)
        
        fetcher.close()


class TestExceptionClasses(unittest.TestCase):
    """Tests for custom exception classes."""
    
    def test_document_retrieval_error(self):
        """Verify DocumentRetrievalError can be raised with message."""
        with self.assertRaises(DocumentRetrievalError) as context:
            raise DocumentRetrievalError("Test error message")
        
        self.assertEqual(str(context.exception), "Test error message")
    
    def test_search_operation_error(self):
        """Verify SearchOperationError can be raised with message."""
        with self.assertRaises(SearchOperationError) as context:
            raise SearchOperationError("Search failed")
        
        self.assertEqual(str(context.exception), "Search failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
