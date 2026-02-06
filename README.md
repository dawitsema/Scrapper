# NC Secretary of State Business Document Fetcher

A Python tool for searching and downloading business registration documents from the North Carolina Secretary of State website.

## Features

- Search businesses by name or partial name
- Automatically extract PDF document links
- Download and save documents locally
- Configurable request delays to be respectful of the server
- Retry logic for handling temporary failures
- Detailed logging of operations

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Command Line

Search and download documents for a specific business:

```bash
python nc_business_doc_fetcher.py "Business Name"
```

Specify a custom output directory:

```bash
python nc_business_doc_fetcher.py "Business Name" --output ./my_documents
```

Set a custom delay between requests:

```bash
python nc_business_doc_fetcher.py "Business Name" --delay 2.0
```

Enable verbose logging:

```bash
python nc_business_doc_fetcher.py "Business Name" --verbose
```

### As a Python Module

```python
from nc_business_doc_fetcher import NCBusinessDocumentFetcher, ScraperConfiguration

# Create configuration
config = ScraperConfiguration(
    storage_directory="./documents",
    request_delay_seconds=2.0
)

# Initialize fetcher
fetcher = NCBusinessDocumentFetcher(config)

# Search and download
results = fetcher.process_search_and_download("Example Corporation")

print(f"Found {results['businesses_found']} businesses")
print(f"Downloaded {results['documents_downloaded']} documents")

# Clean up
fetcher.close()
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `storage_directory` | `./fetched_documents` | Directory to save downloaded PDFs |
| `request_delay_seconds` | `1.5` | Delay between HTTP requests |
| `connection_timeout` | `30` | HTTP connection timeout in seconds |
| `max_retry_attempts` | `3` | Maximum retries for failed requests |

## Output

Downloaded documents are saved with the naming format:
```
{business_name}_{url_hash}_{timestamp}.pdf
```

## Dependencies

- requests - HTTP library
- beautifulsoup4 - HTML parsing
- lxml - Fast XML/HTML parser
- PyPDF2 - PDF handling utilities

## Legal Notice

This tool is for educational and research purposes. Please ensure you comply with the NC Secretary of State website's terms of service and robots.txt. Use responsibly and avoid making excessive requests.

## License

MIT License
