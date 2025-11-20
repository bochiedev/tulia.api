"""
Unit tests for Code Cleanup Analyzer Service

Tests the functionality of detecting:
- Unused imports
- Unused functions
- Unused classes
- Duplicate code blocks
- Deprecated API usage
"""

import pytest
import tempfile
import os
from pathlib import Path
from apps.bot.services.code_cleanup_analyzer import CodeCleanupAnalyzer


class TestCodeCleanupAnalyzer:
    """Test suite for CodeCleanupAnalyzer."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def create_test_file(self, temp_dir: Path, filename: str, content: str) -> Path:
        """Helper to create a test Python file."""
        file_path = temp_dir / filename
        file_path.write_text(content)
        return file_path
    
    # Tests for unused import detection
    
    def test_detect_unused_import_simple(self, temp_dir):
        """Test detection of a simple unused import."""
        content = """
import os
import sys

def main():
    print(sys.version)
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_imports()
        
        # Should detect 'os' as unused
        assert len(unused) == 1
        assert unused[0]['import'] == 'os'
        assert 'test.py' in unused[0]['file']
    
    def test_detect_unused_from_import(self, temp_dir):
        """Test detection of unused 'from X import Y' statements."""
        content = """
from datetime import datetime, timedelta
from typing import List

def get_date():
    return datetime.now()
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_imports()
        
        # Should detect 'timedelta' and 'List' as unused
        unused_names = {item['import'] for item in unused}
        assert 'timedelta' in unused_names
        assert 'List' in unused_names
        assert 'datetime' not in unused_names
    
    def test_detect_unused_import_with_alias(self, temp_dir):
        """Test detection of unused imports with aliases."""
        content = """
import pandas as pd
import numpy as np

def process():
    data = np.array([1, 2, 3])
    return data
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_imports()
        
        # Should detect 'pd' as unused
        assert len(unused) == 1
        assert unused[0]['import'] == 'pd'
    
    def test_no_unused_imports_when_all_used(self, temp_dir):
        """Test that no unused imports are reported when all are used."""
        content = """
import os
import sys

def main():
    print(os.getcwd())
    print(sys.version)
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_imports()
        
        assert len(unused) == 0
    
    def test_import_used_in_attribute_access(self, temp_dir):
        """Test that imports used in attribute access are not flagged."""
        content = """
import datetime

def get_now():
    return datetime.datetime.now()
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_imports()
        
        assert len(unused) == 0
    
    # Tests for unused function detection
    
    def test_detect_unused_function(self, temp_dir):
        """Test detection of unused functions."""
        content = """
def used_function():
    return "used"

def unused_function():
    return "unused"

def main():
    result = used_function()
    print(result)

# Call main to make it "used"
main()
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_functions()
        
        # Should detect 'unused_function' as unused
        unused_names = {item['name'] for item in unused}
        assert 'unused_function' in unused_names
        assert 'used_function' not in unused_names
        assert 'main' not in unused_names
    
    def test_private_functions_not_flagged(self, temp_dir):
        """Test that private functions (starting with _) are not flagged."""
        content = """
def _private_function():
    return "private"

def public_function():
    return "public"
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_functions()
        
        # Should only flag public_function, not _private_function
        unused_names = {item['name'] for item in unused}
        assert 'public_function' in unused_names
        assert '_private_function' not in unused_names
    
    def test_function_called_as_method(self, temp_dir):
        """Test that functions called as methods are not flagged."""
        content = """
def process():
    return "processed"

class Handler:
    def handle(self):
        obj.process()
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_functions()
        
        # 'process' should not be flagged as unused
        unused_names = {item['name'] for item in unused}
        assert 'process' not in unused_names
    
    def test_multiple_files_function_usage(self, temp_dir):
        """Test function usage detection across multiple files."""
        # File 1: defines a function
        content1 = """
def helper_function():
    return "help"
"""
        self.create_test_file(temp_dir, "module1.py", content1)
        
        # File 2: uses the function
        content2 = """
from module1 import helper_function

def main():
    result = helper_function()
"""
        self.create_test_file(temp_dir, "module2.py", content2)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_functions()
        
        # helper_function should not be flagged as unused
        unused_names = {item['name'] for item in unused}
        assert 'helper_function' not in unused_names
    
    # Tests for unused class detection
    
    def test_detect_unused_class(self, temp_dir):
        """Test detection of unused classes."""
        content = """
class UsedClass:
    pass

class UnusedClass:
    pass

def main():
    obj = UsedClass()
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_classes()
        
        # Should detect 'UnusedClass' as unused
        assert len(unused) == 1
        assert unused[0]['name'] == 'UnusedClass'
    
    def test_class_used_in_inheritance(self, temp_dir):
        """Test that classes used in inheritance are not flagged."""
        content = """
class BaseClass:
    pass

class DerivedClass(BaseClass):
    pass

obj = DerivedClass()
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_classes()
        
        # Neither class should be flagged
        unused_names = {item['name'] for item in unused}
        assert 'BaseClass' not in unused_names
        assert 'DerivedClass' not in unused_names
    
    def test_private_classes_not_flagged(self, temp_dir):
        """Test that private classes are not flagged."""
        content = """
class _PrivateClass:
    pass

class PublicClass:
    pass
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        unused = analyzer.find_unused_classes()
        
        # Should only flag PublicClass
        unused_names = {item['name'] for item in unused}
        assert 'PublicClass' in unused_names
        assert '_PrivateClass' not in unused_names
    
    # Tests for duplicate code detection
    
    def test_detect_duplicate_functions(self, temp_dir):
        """Test detection of duplicate function bodies."""
        content = """
def function_a():
    x = 1
    y = 2
    z = x + y
    return z

def function_b():
    x = 1
    y = 2
    z = x + y
    return z

def function_c():
    return "different"
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        duplicates = analyzer.find_duplicate_code(min_lines=3)
        
        # Should detect function_a and function_b as duplicates
        assert len(duplicates) > 0
        # Check that we found at least one duplicate pair
        found_duplicate = any(dup['count'] >= 2 for dup in duplicates)
        assert found_duplicate
    
    def test_no_duplicates_for_short_functions(self, temp_dir):
        """Test that short functions are not flagged as duplicates."""
        content = """
def short_a():
    return 1

def short_b():
    return 1
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        duplicates = analyzer.find_duplicate_code(min_lines=5)
        
        # Should not detect duplicates for very short functions
        assert len(duplicates) == 0
    
    def test_duplicate_across_files(self, temp_dir):
        """Test detection of duplicates across multiple files."""
        content1 = """
def process_data():
    data = []
    for i in range(10):
        data.append(i * 2)
    return data
"""
        content2 = """
def handle_data():
    data = []
    for i in range(10):
        data.append(i * 2)
    return data
"""
        self.create_test_file(temp_dir, "file1.py", content1)
        self.create_test_file(temp_dir, "file2.py", content2)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        duplicates = analyzer.find_duplicate_code(min_lines=3)
        
        # Should detect duplicates across files
        assert len(duplicates) > 0
    
    # Tests for deprecated API usage detection
    
    def test_detect_deprecated_django_url(self, temp_dir):
        """Test detection of deprecated django.conf.urls.url."""
        content = """
from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^test/$', views.test_view),
]
"""
        self.create_test_file(temp_dir, "urls.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        deprecated = analyzer.find_deprecated_api_usage()
        
        # Should detect deprecated url import
        assert len(deprecated) > 0
        assert any('django.conf.urls' in item['code'] for item in deprecated)
    
    def test_detect_deprecated_ugettext(self, temp_dir):
        """Test detection of deprecated ugettext."""
        content = """
from django.utils.translation import ugettext as _

def my_view():
    message = _("Hello")
"""
        self.create_test_file(temp_dir, "views.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        deprecated = analyzer.find_deprecated_api_usage()
        
        # Should detect deprecated ugettext
        assert len(deprecated) > 0
        assert any('translation' in item['code'] and 'ugettext' in item['code'] for item in deprecated)
    
    def test_detect_deprecated_collections(self, temp_dir):
        """Test detection of deprecated collections imports."""
        content = """
from collections import Callable, Iterable

def process(items: Iterable):
    pass
"""
        self.create_test_file(temp_dir, "utils.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        deprecated = analyzer.find_deprecated_api_usage()
        
        # Should detect deprecated collections usage
        assert len(deprecated) > 0
        assert any('collections' in item['code'] for item in deprecated)
    
    def test_no_deprecated_api_in_modern_code(self, temp_dir):
        """Test that modern code doesn't trigger false positives."""
        content = """
from django.urls import path
from django.utils.translation import gettext as _

def my_view():
    message = _("Hello")
"""
        self.create_test_file(temp_dir, "views.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        deprecated = analyzer.find_deprecated_api_usage()
        
        # Should not detect any deprecated usage
        assert len(deprecated) == 0
    
    # Tests for comprehensive report generation
    
    def test_generate_comprehensive_report(self, temp_dir):
        """Test generation of comprehensive cleanup report."""
        content = """
import os
import sys

class UnusedClass:
    pass

def unused_function():
    return "unused"

def main():
    print(sys.version)
"""
        self.create_test_file(temp_dir, "test.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        report = analyzer.generate_report()
        
        # Report should contain all analysis categories
        assert 'unused_imports' in report
        assert 'unused_functions' in report
        assert 'unused_classes' in report
        assert 'duplicate_code' in report
        assert 'deprecated_api' in report
        
        # Should have detected some issues
        assert len(report['unused_imports']) > 0
        assert len(report['unused_functions']) > 0
        assert len(report['unused_classes']) > 0
    
    def test_analyzer_handles_syntax_errors_gracefully(self, temp_dir):
        """Test that analyzer handles files with syntax errors."""
        content = """
def broken_function(
    # Missing closing parenthesis
    return "broken"
"""
        self.create_test_file(temp_dir, "broken.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        
        # Should not raise an exception
        unused_imports = analyzer.find_unused_imports()
        unused_functions = analyzer.find_unused_functions()
        
        # Should return empty results for broken file
        assert isinstance(unused_imports, list)
        assert isinstance(unused_functions, list)
    
    def test_analyzer_with_single_file(self, temp_dir):
        """Test analyzer with a single file instead of directory."""
        content = """
import os

def main():
    pass
"""
        file_path = self.create_test_file(temp_dir, "single.py", content)
        
        analyzer = CodeCleanupAnalyzer(str(file_path))
        unused = analyzer.find_unused_imports()
        
        # Should work with single file
        assert len(unused) == 1
        assert unused[0]['import'] == 'os'
    
    def test_analyzer_with_empty_directory(self, temp_dir):
        """Test analyzer with empty directory."""
        analyzer = CodeCleanupAnalyzer(str(temp_dir))
        report = analyzer.generate_report()
        
        # Should return empty results
        assert len(report['unused_imports']) == 0
        assert len(report['unused_functions']) == 0
        assert len(report['unused_classes']) == 0
