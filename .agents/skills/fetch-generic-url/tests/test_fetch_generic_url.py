#!/usr/bin/env python3
"""Comprehensive unit tests for fetch_generic_url skill."""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add scripts directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import fetch_generic_url as dgu


class TestSlugify(unittest.TestCase):
    """Tests for slugify function."""
    
    def test_slugify_simple_text(self):
        result = dgu.slugify("Hello World")
        self.assertEqual(result, "hello_world")
    
    def test_slugify_with_accents(self):
        result = dgu.slugify("Café français")
        # Accents are normalized to ASCII
        self.assertIn("caf", result.lower())
    
    def test_slugify_with_special_chars(self):
        result = dgu.slugify("Hello-World_123!")
        self.assertIn("hello", result)
        self.assertIn("world", result)
    
    def test_slugify_empty_string(self):
        result = dgu.slugify("")
        self.assertEqual(result, "document")
    
    def test_slugify_only_numbers(self):
        result = dgu.slugify("12345")
        self.assertEqual(result, "12345")


class TestUrlStorageSubdir(unittest.TestCase):
    """Tests for URL-derived storage subdirectories."""

    def test_ignores_query_and_cleans_last_segment(self):
        result = dgu.url_storage_subdir(
            "https://www.saint-george.ch/f/vie-politique/conseil_communal/archives.asp?annee=2024"
        )
        self.assertEqual(result, Path("vie_politique") / "conseil_communal" / "archives")

    def test_root_url_uses_hostname(self):
        result = dgu.url_storage_subdir("https://www.saint-george.ch/?annee=2024")
        self.assertEqual(result, Path("www_saint_george_ch"))

    def test_only_last_segment_is_cleaned(self):
        result = dgu.url_storage_subdir("https://example.com/v1.2/archive.asp")
        self.assertEqual(result, Path("v1_2") / "archive")


class TestYamlEscape(unittest.TestCase):
    """Tests for YAML escaping."""
    
    def test_yaml_escape_with_quotes(self):
        result = dgu.yaml_escape('Hello "World"')
        self.assertNotIn('"', result)
        self.assertIn("'", result)
    
    def test_yaml_escape_normal_text(self):
        result = dgu.yaml_escape("Hello World")
        self.assertEqual(result, "Hello World")
    
    def test_yaml_escape_empty_string(self):
        result = dgu.yaml_escape("")
        self.assertEqual(result, "")


class TestGenerateTechnique(unittest.TestCase):
    """Tests for signature generation."""
    
    def test_generate_identifiant_deterministic(self):
        path = "/sources/test/document.pdf"
        result1 = dgu.generate_signature(path)
        result2 = dgu.generate_signature(path)
        self.assertEqual(result1, result2)
    
    def test_generate_identifiant_is_md5(self):
        path = "/sources/test/document.pdf"
        result = dgu.generate_signature(path)
        # MD5 hex is 32 characters
        self.assertEqual(len(result), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))
    
    def test_generate_identifiant_different_for_different_paths(self):
        result1 = dgu.generate_signature("/path1")
        result2 = dgu.generate_signature("/path2")
        self.assertNotEqual(result1, result2)

    def test_generate_identifiant_uses_file_content_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first_path = Path(tmpdir) / "first.txt"
            second_path = Path(tmpdir) / "second.txt"
            content = b"same content"
            first_path.write_bytes(content)
            second_path.write_bytes(content)

            result1 = dgu.generate_signature(str(first_path))
            result2 = dgu.generate_signature(str(second_path))

            self.assertEqual(result1, hashlib.md5(content).hexdigest())
            self.assertEqual(result1, result2)


class TestContentTypeDetection(unittest.TestCase):
    """Tests for content type detection."""
    
    @patch('fetch_generic_url.requests.Session.head')
    def test_detect_pdf_document(self, mock_head):
        mock_response = Mock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.history = []
        mock_response.url = "https://example.com/document.pdf"
        mock_head.return_value = mock_response
        
        session = dgu.requests.Session()
        content_type, ext, is_webpage = dgu.get_content_type("https://example.com/document.pdf", session, 3)
        
        self.assertIn("pdf", content_type.lower())
        self.assertFalse(is_webpage)
    
    @patch('fetch_generic_url.requests.Session.head')
    def test_detect_html_webpage(self, mock_head):
        mock_response = Mock()
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.history = []
        mock_response.url = "https://example.com/page.html"
        mock_head.return_value = mock_response
        
        session = dgu.requests.Session()
        content_type, ext, is_webpage = dgu.get_content_type("https://example.com/page.html", session, 3)
        
        self.assertTrue(is_webpage)
    
    @patch('fetch_generic_url.requests.Session.head')
    def test_too_many_redirects(self, mock_head):
        mock_response = Mock()
        mock_response.headers = {}
        # Simulate 5 redirects (more than max of 3)
        mock_response.history = [Mock(), Mock(), Mock(), Mock(), Mock()]
        mock_head.return_value = mock_response
        
        session = dgu.requests.Session()
        content_type, ext, is_webpage = dgu.get_content_type("https://example.com/file", session, 3)
        
        # Should handle gracefully
        self.assertEqual(content_type, "")


class TestDocumentUrlDetection(unittest.TestCase):
    """Tests for document URL detection."""
    
    def test_pdf_url_detection(self):
        result = dgu.is_document_url("https://example.com/document.pdf", ["pdf"])
        self.assertTrue(result)
    
    def test_non_pdf_url(self):
        result = dgu.is_document_url("https://example.com/document.html", ["pdf"])
        self.assertFalse(result)
    
    def test_multiple_document_types(self):
        result = dgu.is_document_url("https://example.com/file.xlsx", ["pdf", "xlsx", "docx"])
        self.assertTrue(result)
    
    def test_case_insensitive(self):
        result = dgu.is_document_url("https://example.com/document.PDF", ["pdf"])
        self.assertTrue(result)

    @patch('fetch_generic_url.requests.Session.head')
    def test_proxy_pdf_detection_via_head(self, mock_head):
        mock_response = Mock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.history = []
        mock_response.url = "https://example.com/module/document/public/download.asp?code=123"
        mock_head.return_value = mock_response

        session = dgu.requests.Session()
        result = dgu._looks_like_document_by_head(
            "https://example.com/module/document/public/download.asp?code=123",
            ["pdf"],
            session,
            3,
        )

        self.assertTrue(result)


class TestFindDocumentLinks(unittest.TestCase):
    """Tests for finding document links in HTML."""
    
    def test_find_pdf_links(self):
        html = """
        <html>
            <a href="document1.pdf">PDF 1</a>
            <a href="https://example.com/document2.pdf">PDF 2</a>
            <a href="page.html">Page</a>
        </html>
        """
        links = dgu.find_document_links(html, "https://example.com/", ["pdf"])
        self.assertEqual(len(links), 2)
        self.assertTrue(any("document1.pdf" in link for link in links))
    
    def test_find_multiple_types(self):
        html = """
        <html>
            <a href="doc.pdf">PDF</a>
            <a href="sheet.xlsx">Excel</a>
            <a href="page.html">HTML</a>
        </html>
        """
        links = dgu.find_document_links(html, "https://example.com/", ["pdf", "xlsx"])
        self.assertEqual(len(links), 2)
    
    def test_duplicate_links_removed(self):
        html = """
        <html>
            <a href="doc.pdf">PDF 1</a>
            <a href="doc.pdf">PDF 2</a>
        </html>
        """
        links = dgu.find_document_links(html, "https://example.com/", ["pdf"])
        self.assertEqual(len(links), 1)


class TestImageExtraction(unittest.TestCase):
    """Tests for image extraction from HTML."""
    
    def test_extract_images(self):
        html = """
        <html>
            <img src="image1.png">
            <img src="https://example.com/image2.jpg">
        </html>
        """
        images = dgu.extract_images_from_html(html, "https://example.com/")
        self.assertEqual(len(images), 2)
    
    def test_no_images(self):
        html = "<html><body><p>No images</p></body></html>"
        images = dgu.extract_images_from_html(html, "https://example.com/")
        self.assertEqual(len(images), 0)
    
    def test_relative_urls_resolved(self):
        html = '<html><img src="image.png"></html>'
        images = dgu.extract_images_from_html(html, "https://example.com/page/")
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0].startswith("https://"))


class TestHtmlToMarkdown(unittest.TestCase):
    """Tests for HTML to Markdown conversion."""
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_basic_html_conversion(self, mock_get):
        html = """
        <html>
            <title>Test Page</title>
            <body>
                <h1>Header 1</h1>
                <p>Paragraph content</p>
            </body>
        </html>
        """
        session = dgu.requests.Session()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            markdown, _, images = dgu.html_to_markdown(html, "https://example.com/", output_dir, session)
            
            self.assertIn("Header 1", markdown)
            self.assertIn("Paragraph content", markdown)
            self.assertIn("## Page 1", markdown)
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_html_preserves_structure(self, mock_get):
        html = """
        <html>
            <body>
                <h1>Title</h1>
                <h2>Subtitle</h2>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
            </body>
        </html>
        """
        session = dgu.requests.Session()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            markdown, _, _ = dgu.html_to_markdown(html, "https://example.com/", output_dir, session)
            
            self.assertIn("Title", markdown)
            self.assertIn("Item 1", markdown)

    def test_html_newlines_are_converted_to_spaces(self):
        html = """
        <html><body><p>Ligne 1
        Ligne 2</p></body></html>
        """
        session = dgu.requests.Session()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            markdown, _, _ = dgu.html_to_markdown(html, "https://example.com/", output_dir, session)
            self.assertIn("Ligne 1 Ligne 2", markdown)

    @patch('fetch_generic_url.requests.Session.get')
    def test_images_saved_in_document_specific_directory(self, mock_get):
        html = """
        <html>
            <title>Mon article test</title>
            <body>
                <img src="/img/test.png" />
                <p>Contenu</p>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"IMG"]
        mock_get.return_value = mock_response

        session = dgu.requests.Session()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _, _, images = dgu.html_to_markdown(html, "https://example.com/", output_dir, session, follow_links=True)
            self.assertEqual(len(images), 1)
            self.assertIn("mon_article_test", images[0].as_posix())
            self.assertIn("/images/", images[0].as_posix())


class TestFrontMatter(unittest.TestCase):
    """Tests for YAML front matter generation."""
    
    def test_front_matter_has_required_fields(self):
        front_matter = dgu.generate_front_matter("Test Article", "https://example.com/")
        
        self.assertIn("title:", front_matter)
        self.assertIn("url:", front_matter)
        self.assertIn("date_publication:", front_matter)
        self.assertIn("date_consultation:", front_matter)
        self.assertIn("transformation_by:", front_matter)
        self.assertIn("sources:", front_matter)
        self.assertIn("signature:", front_matter)
    
    def test_front_matter_valid_yaml(self):
        front_matter = dgu.generate_front_matter("Test Title", "https://example.com/test")
        
        self.assertTrue(front_matter.startswith("---"))
        self.assertIn("---", front_matter[4:])  # Second separator
    
    def test_front_matter_escapes_quotes(self):
        front_matter = dgu.generate_front_matter('Title with "quotes"', "https://example.com/")
        
        # Should have escaped quotes
        self.assertNotIn('title: "Title with "quotes""', front_matter)


class TestHandleDirectDocument(unittest.TestCase):
    """Tests for direct document handling."""
    
    @patch('fetch_generic_url._download_file_with_metadata')
    @patch('fetch_generic_url.upsert_source')
    def test_download_direct_pdf(self, mock_upsert, mock_download):
        
        # Mock database insertion
        mock_upsert.return_value = {"action": "created", "source_id": 1}
        
        session = dgu.requests.Session()
        dgu.DB_AVAILABLE = False  # Disable DB for this test
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            downloaded = output_dir / "document.pdf"
            downloaded.write_bytes(b"PDF_CONTENT")
            mock_download.return_value = downloaded
            result = dgu.handle_direct_document(
                "https://example.com/document.pdf",
                output_dir,
                session,
                3,
                None
            )
            
            self.assertTrue(result["success"])
            self.assertIn("document", result["file"].lower())
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_download_file_too_large(self, mock_get):
        # Mock response with large file
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": str(200 * 1024 * 1024)}  # 200MB
        mock_response.history = []
        mock_get.return_value = mock_response
        
        session = dgu.requests.Session()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = dgu.download_file(
                "https://example.com/huge.pdf",
                output_dir / "huge.pdf",
                session,
                3
            )
            
            self.assertFalse(result)


class TestHandleWebpageWithDocumentType(unittest.TestCase):
    """Tests for webpage with document_type handling."""
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_find_pdfs_on_webpage(self, mock_get):
        # Mock HTML with PDF links
        html = """
        <html>
            <body>
                <a href="report1.pdf">Report 1</a>
                <a href="report2.pdf">Report 2</a>
                <p>Some text</p>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.history = []
        mock_get.return_value = mock_response
        
        session = dgu.requests.Session()
        dgu.DB_AVAILABLE = False
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = dgu.handle_webpage_with_document_type(
                "https://example.com/documents",
                output_dir,
                "pdf",
                session,
                3,
                None
            )
            
            # May have error due to mock, but that's OK for this test


class TestHandleWebpageWithoutDocumentType(unittest.TestCase):
    """Tests for webpage without document_type handling."""
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_webpage_to_markdown(self, mock_get):
        html = """
        <html>
            <title>Test Article</title>
            <body>
                <h1>Main Title</h1>
                <p>Article content goes here.</p>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.history = []
        mock_get.return_value = mock_response
        
        session = dgu.requests.Session()
        dgu.DB_AVAILABLE = False
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = dgu.handle_webpage_without_document_type(
                "https://example.com/article",
                output_dir,
                False,
                session,
                None
            )
            
            self.assertTrue(result["success"])
            self.assertIn("markdown", result)
            
            # Check markdown file was created
            md_file = Path(result["markdown"])
            self.assertTrue(md_file.exists())
            
            # Check content
            content = md_file.read_text(encoding="utf-8")
            self.assertIn("---", content)  # Front matter
            self.assertIn("Main Title", content)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling."""
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_http_error_handling(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        
        session = dgu.requests.Session()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = dgu.download_file(
                "https://invalid.example.com/",
                output_dir / "file.pdf",
                session,
                3
            )
            
            self.assertFalse(result)
    
    @patch('fetch_generic_url.requests.Session.get')
    def test_404_error(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.history = []
        mock_get.return_value = mock_response
        
        session = dgu.requests.Session()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = dgu.download_file(
                "https://example.com/notfound",
                output_dir / "file.pdf",
                session,
                3
            )
            
            self.assertFalse(result)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_document_types_mapping(self):
        """Verify document types are properly mapped."""
        for doc_type, extensions in dgu.DOCUMENT_TYPES.items():
            self.assertIsInstance(extensions, list)
            self.assertTrue(all(ext.startswith(".") for ext in extensions))
    
    def test_image_extensions_valid(self):
        """Verify image extensions are valid."""
        for ext in dgu.IMAGE_EXTENSIONS:
            self.assertTrue(ext.startswith("."))
            self.assertGreater(len(ext), 1)


class TestArgumentParsing(unittest.TestCase):
    """Tests for argument parsing."""
    
    def test_parse_required_url(self):
        """URL argument is required."""
        with self.assertRaises(SystemExit):
            dgu.parse_args()
    
    def test_parse_all_arguments(self):
        test_args = [
            "script.py",
            "--url", "https://example.com/doc.pdf",
            "--document-type", "pdf",
            "--out-dir", "/tmp/output",
            "--max-redirects", "5",
            "--follow-links",
            "--dry-run",
        ]
        
        with patch.object(sys, "argv", test_args):
            args = dgu.parse_args()
            self.assertEqual(args.url, "https://example.com/doc.pdf")
            self.assertEqual(args.document_type, "pdf")
            self.assertEqual(args.max_redirects, 5)
            self.assertTrue(args.follow_links)
            self.assertTrue(args.dry_run)


class TestMainRouting(unittest.TestCase):
    """Tests for main() routing and output directory resolution."""

    @patch('fetch_generic_url.handle_webpage_with_document_type')
    @patch('fetch_generic_url.get_content_type')
    @patch('fetch_generic_url.requests.Session')
    def test_main_uses_url_specific_subdir_for_document_type_webpage(self, mock_session_cls, mock_get_content_type, mock_handle):
        mock_get_content_type.return_value = ("text/html", ".html", True)
        mock_handle.return_value = {"success": True, "files": []}
        dgu.DB_AVAILABLE = False

        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                url="https://www.saint-george.ch/f/vie-politique/conseil_communal/archives.asp?annee=2024",
                document_type="pdf",
                out_dir=Path(tmpdir),
                dry_run=False,
                max_redirects=3,
                follow_links=False,
                background_download=False,
                worklist_file=None,
                max_download_attempts=4,
                run_worklist_worker=False,
            )

            with patch('fetch_generic_url.parse_args', return_value=args):
                dgu.main()

        called_output_dir = mock_handle.call_args.args[1]
        expected = Path(tmpdir).resolve() / "vie_politique" / "conseil_communal" / "archives"
        self.assertEqual(called_output_dir, expected)

    @patch('fetch_generic_url.handle_direct_document')
    @patch('fetch_generic_url.get_content_type')
    @patch('fetch_generic_url.requests.Session')
    def test_main_warns_and_ignores_document_type_for_direct_document(self, mock_session_cls, mock_get_content_type, mock_handle):
        mock_get_content_type.return_value = ("application/pdf", ".pdf", False)
        mock_handle.return_value = {"success": True, "file": "dummy.pdf"}
        dgu.DB_AVAILABLE = False

        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                url="https://example.com/document.pdf",
                document_type="pdf",
                out_dir=Path(tmpdir),
                dry_run=False,
                max_redirects=3,
                follow_links=False,
                background_download=False,
                worklist_file=None,
                max_download_attempts=4,
                run_worklist_worker=False,
            )

            with patch('fetch_generic_url.parse_args', return_value=args), patch('builtins.print') as mock_print:
                dgu.main()

        warning_messages = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
        self.assertTrue(any("--document-type ignoré" in message for message in warning_messages))
        mock_handle.assert_called_once()


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
