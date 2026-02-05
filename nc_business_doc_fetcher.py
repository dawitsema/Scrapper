#!/usr/bin/env python3
"""
NC Secretary of State Business Document Fetcher

This module provides functionality to search and retrieve business registration
documents from the North Carolina Secretary of State website.

Author: Custom Implementation
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup

# Configure module-level logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
module_logger = logging.getLogger(__name__)

# Constants for filename generation
FILENAME_MAX_LENGTH = 50


@dataclass
class BusinessRecord:
    """Represents a single business entity from search results."""
    entity_name: str
    sos_identifier: str
    status_text: str
    date_registered: str
    detail_link: str
    pdf_documents: list = field(default_factory=list)


@dataclass
class ScraperConfiguration:
    """Configuration options for the document fetcher."""
    target_base_url: str = "https://www.sosnc.gov"
    search_endpoint: str = "/online_services/search/by_title/_Business_Registration"
    storage_directory: str = "./fetched_documents"
    request_delay_seconds: float = 1.5
    connection_timeout: int = 30
    max_retry_attempts: int = 3
    http_user_agent: str = "NCBusinessDocFetcher/1.0"


class DocumentRetrievalError(Exception):
    """Raised when document download fails."""
    pass


class SearchOperationError(Exception):
    """Raised when business search encounters an error."""
    pass


class NCBusinessDocumentFetcher:
    """
    Fetches business registration documents from NC Secretary of State.
    
    This class handles searching for businesses, extracting document links,
    and downloading PDF files to local storage.
    """
    
    def __init__(self, config: Optional[ScraperConfiguration] = None):
        """Initialize the fetcher with optional configuration."""
        self._config = config or ScraperConfiguration()
        self._http_session = self._create_session()
        self._storage_path = Path(self._config.storage_directory)
        self._ensure_storage_exists()
        
    def _create_session(self) -> requests.Session:
        """Create and configure HTTP session."""
        http_session = requests.Session()
        http_session.headers.update({
            "User-Agent": self._config.http_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        return http_session
    
    def _ensure_storage_exists(self) -> None:
        """Create storage directory if it doesn't exist."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
        module_logger.info(f"Document storage: {self._storage_path.absolute()}")
    
    def _perform_request(self, target_url: str, retry_count: int = 0) -> requests.Response:
        """Execute HTTP request with retry logic."""
        try:
            time.sleep(self._config.request_delay_seconds)
            response = self._http_session.get(
                target_url,
                timeout=self._config.connection_timeout
            )
            response.raise_for_status()
            return response
        except requests.RequestException as req_error:
            if retry_count < self._config.max_retry_attempts:
                wait_duration = (retry_count + 1) * 2
                module_logger.warning(
                    f"Request failed, retrying in {wait_duration}s: {req_error}"
                )
                time.sleep(wait_duration)
                return self._perform_request(target_url, retry_count + 1)
            raise SearchOperationError(f"Request failed after retries: {req_error}")
    
    def search_businesses(self, query_term: str) -> list[BusinessRecord]:
        """
        Search for businesses matching the query term.
        
        Args:
            query_term: Business name or partial name to search
            
        Returns:
            List of BusinessRecord objects matching the search
        """
        module_logger.info(f"Searching for businesses: '{query_term}'")
        
        search_url = urljoin(
            self._config.target_base_url,
            self._config.search_endpoint
        )
        
        query_params = urlencode({"Words": query_term})
        full_search_url = f"{search_url}?{query_params}"
        
        try:
            response = self._perform_request(full_search_url)
            return self._extract_business_records(response.text)
        except Exception as err:
            module_logger.error(f"Search operation failed: {err}")
            raise SearchOperationError(f"Unable to search: {err}")
    
    def _extract_business_records(self, html_content: str) -> list[BusinessRecord]:
        """Parse HTML and extract business records from search results."""
        parsed_html = BeautifulSoup(html_content, "lxml")
        business_list = []
        
        # Look for result table rows
        result_table = parsed_html.find("table", {"class": re.compile(r".*result.*", re.I)})
        if not result_table:
            result_table = parsed_html.find("table", {"id": re.compile(r".*search.*", re.I)})
        
        if not result_table:
            module_logger.warning("No results table found in response")
            return business_list
        
        table_rows = result_table.find_all("tr")
        
        for row in table_rows[1:]:  # Skip header row
            cells = row.find_all("td")
            if len(cells) >= 3:
                name_cell = cells[0]
                link_element = name_cell.find("a")
                
                if link_element:
                    record = BusinessRecord(
                        entity_name=link_element.get_text(strip=True),
                        sos_identifier=cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        status_text=cells[2].get_text(strip=True) if len(cells) > 2 else "",
                        date_registered=cells[3].get_text(strip=True) if len(cells) > 3 else "",
                        detail_link=urljoin(self._config.target_base_url, link_element.get("href", ""))
                    )
                    business_list.append(record)
        
        module_logger.info(f"Found {len(business_list)} business records")
        return business_list
    
    def fetch_business_documents(self, business: BusinessRecord) -> list[str]:
        """
        Retrieve all PDF documents for a specific business.
        
        Args:
            business: BusinessRecord to fetch documents for
            
        Returns:
            List of paths to downloaded PDF files
        """
        module_logger.info(f"Fetching documents for: {business.entity_name}")
        
        try:
            response = self._perform_request(business.detail_link)
            pdf_links = self._locate_pdf_links(response.text)
            
            downloaded_paths = []
            for pdf_url in pdf_links:
                try:
                    saved_path = self._download_pdf_file(pdf_url, business.entity_name)
                    downloaded_paths.append(saved_path)
                except DocumentRetrievalError as doc_err:
                    module_logger.error(f"Failed to download PDF: {doc_err}")
            
            return downloaded_paths
            
        except Exception as err:
            module_logger.error(f"Document fetch failed: {err}")
            return []
    
    def _locate_pdf_links(self, html_content: str) -> list[str]:
        """Extract PDF document URLs from business detail page."""
        parsed_html = BeautifulSoup(html_content, "lxml")
        pdf_urls = []
        
        # Find all links ending in .pdf
        all_links = parsed_html.find_all("a", href=True)
        for link in all_links:
            href = link.get("href", "")
            if href.lower().endswith(".pdf"):
                full_url = urljoin(self._config.target_base_url, href)
                if full_url not in pdf_urls:
                    pdf_urls.append(full_url)
        
        module_logger.info(f"Located {len(pdf_urls)} PDF documents")
        return pdf_urls
    
    def _download_pdf_file(self, pdf_url: str, business_name: str) -> str:
        """Download a PDF file and save to storage directory."""
        try:
            response = self._perform_request(pdf_url)
            
            # Generate safe filename
            safe_name = re.sub(r'[^\w\s-]', '', business_name)[:FILENAME_MAX_LENGTH]
            url_hash = hashlib.md5(pdf_url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            filename = f"{safe_name}_{url_hash}_{timestamp}.pdf"
            file_path = self._storage_path / filename
            
            with open(file_path, "wb") as pdf_file:
                pdf_file.write(response.content)
            
            module_logger.info(f"Saved document: {filename}")
            return str(file_path)
            
        except Exception as err:
            raise DocumentRetrievalError(f"PDF download failed: {err}")
    
    def process_search_and_download(self, search_query: str) -> dict:
        """
        Complete workflow: search for businesses and download all documents.
        
        Args:
            search_query: Business name search term
            
        Returns:
            Dictionary with results summary
        """
        results_summary = {
            "search_query": search_query,
            "businesses_found": 0,
            "documents_downloaded": 0,
            "downloaded_files": [],
            "errors": []
        }
        
        try:
            businesses = self.search_businesses(search_query)
            results_summary["businesses_found"] = len(businesses)
            
            for business in businesses:
                doc_paths = self.fetch_business_documents(business)
                results_summary["documents_downloaded"] += len(doc_paths)
                results_summary["downloaded_files"].extend(doc_paths)
                
        except SearchOperationError as search_err:
            results_summary["errors"].append(str(search_err))
        
        return results_summary
    
    def close(self) -> None:
        """Clean up HTTP session."""
        self._http_session.close()


def parse_command_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    arg_parser = argparse.ArgumentParser(
        description="Fetch business documents from NC Secretary of State",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nc_business_doc_fetcher.py "Acme Corporation"
  python nc_business_doc_fetcher.py "Tech Solutions" --output ./my_docs
  python nc_business_doc_fetcher.py "Example LLC" --delay 2.5
        """
    )
    
    arg_parser.add_argument(
        "business_query",
        type=str,
        help="Business name or partial name to search"
    )
    
    arg_parser.add_argument(
        "--output", "-o",
        type=str,
        default="./fetched_documents",
        help="Directory to save downloaded documents (default: ./fetched_documents)"
    )
    
    arg_parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.5,
        help="Delay between requests in seconds (default: 1.5)"
    )
    
    arg_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose debug logging"
    )
    
    return arg_parser.parse_args()


def main() -> int:
    """Main entry point for the document fetcher."""
    args = parse_command_arguments()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    config = ScraperConfiguration(
        storage_directory=args.output,
        request_delay_seconds=args.delay
    )
    
    fetcher = NCBusinessDocumentFetcher(config)
    
    try:
        results = fetcher.process_search_and_download(args.business_query)
        
        print("\n" + "=" * 60)
        print("DOCUMENT FETCH RESULTS")
        print("=" * 60)
        print(f"Search Query:        {results['search_query']}")
        print(f"Businesses Found:    {results['businesses_found']}")
        print(f"Documents Downloaded: {results['documents_downloaded']}")
        
        if results['downloaded_files']:
            print("\nDownloaded Files:")
            for file_path in results['downloaded_files']:
                print(f"  - {file_path}")
        
        if results['errors']:
            print("\nErrors Encountered:")
            for error in results['errors']:
                print(f"  ! {error}")
        
        print("=" * 60)
        
        return 0 if not results['errors'] else 1
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    finally:
        fetcher.close()


if __name__ == "__main__":
    sys.exit(main())
