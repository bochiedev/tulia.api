"""
Code Cleanup Analyzer Service

This service analyzes Python code to identify:
- Unused imports
- Unused functions and classes
- Duplicate code blocks
- Deprecated API usage

Used for maintaining code quality and removing technical debt.
"""

import ast
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import re


class CodeCleanupAnalyzer:
    """Analyzes Python code for cleanup opportunities."""
    
    def __init__(self, directory: str):
        """
        Initialize the analyzer.
        
        Args:
            directory: Root directory to analyze
        """
        self.directory = Path(directory)
        self.python_files: List[Path] = []
        self._scan_directory()
    
    def _scan_directory(self) -> None:
        """Scan directory for Python files."""
        if self.directory.is_file():
            self.python_files = [self.directory]
        else:
            self.python_files = list(self.directory.rglob("*.py"))
    
    def find_unused_imports(self) -> List[Dict[str, any]]:
        """
        Find unused imports across all Python files.
        
        Returns:
            List of dicts with file path, line number, and unused import name
        """
        unused_imports = []
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=str(file_path))
                
                # Extract imports
                imports = self._extract_imports(tree)
                
                # Extract all names used in the file
                used_names = self._extract_used_names(tree)
                
                # Find unused imports
                for import_info in imports:
                    import_name = import_info['name']
                    if import_name not in used_names:
                        unused_imports.append({
                            'file': str(file_path.relative_to(self.directory.parent)),
                            'line': import_info['line'],
                            'import': import_name,
                            'statement': import_info['statement']
                        })
            
            except (SyntaxError, UnicodeDecodeError):
                # Skip files with syntax errors or encoding issues
                continue
        
        return unused_imports
    
    def _extract_imports(self, tree: ast.AST) -> List[Dict[str, any]]:
        """Extract all imports from an AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split('.')[0]
                    imports.append({
                        'name': name,
                        'line': node.lineno,
                        'statement': f"import {alias.name}"
                    })
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        if alias.name == '*':
                            continue  # Skip wildcard imports
                        name = alias.asname if alias.asname else alias.name
                        imports.append({
                            'name': name,
                            'line': node.lineno,
                            'statement': f"from {node.module} import {alias.name}"
                        })
        
        return imports
    
    def _extract_used_names(self, tree: ast.AST) -> Set[str]:
        """Extract all names used in the code (excluding imports)."""
        used_names = set()
        
        class NameVisitor(ast.NodeVisitor):
            def __init__(self):
                self.in_import = False
            
            def visit_Import(self, node):
                self.in_import = True
                self.generic_visit(node)
                self.in_import = False
            
            def visit_ImportFrom(self, node):
                self.in_import = True
                self.generic_visit(node)
                self.in_import = False
            
            def visit_Name(self, node):
                if not self.in_import:
                    used_names.add(node.id)
                self.generic_visit(node)
            
            def visit_Attribute(self, node):
                # For attributes like obj.method, we care about 'obj'
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
                self.generic_visit(node)
        
        visitor = NameVisitor()
        visitor.visit(tree)
        
        return used_names
    
    def find_unused_functions(self) -> List[Dict[str, any]]:
        """
        Find functions that are never called.
        
        Returns:
            List of dicts with file path, line number, and function name
        """
        # Build a map of all defined functions
        defined_functions: Dict[str, List[Dict]] = defaultdict(list)
        called_functions: Set[str] = set()
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=str(file_path))
                
                # Extract function definitions
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Skip special methods and private methods (often used via introspection)
                        if not node.name.startswith('_'):
                            defined_functions[node.name].append({
                                'file': str(file_path.relative_to(self.directory.parent)),
                                'line': node.lineno,
                                'name': node.name
                            })
                
                # Extract function calls
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            called_functions.add(node.func.id)
                        elif isinstance(node.func, ast.Attribute):
                            called_functions.add(node.func.attr)
            
            except (SyntaxError, UnicodeDecodeError):
                continue
        
        # Find unused functions
        unused_functions = []
        for func_name, definitions in defined_functions.items():
            if func_name not in called_functions:
                unused_functions.extend(definitions)
        
        return unused_functions
    
    def find_unused_classes(self) -> List[Dict[str, any]]:
        """
        Find classes that are never instantiated or referenced.
        
        Returns:
            List of dicts with file path, line number, and class name
        """
        # Build a map of all defined classes
        defined_classes: Dict[str, List[Dict]] = defaultdict(list)
        used_classes: Set[str] = set()
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=str(file_path))
                
                # Extract class definitions
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Skip private classes
                        if not node.name.startswith('_'):
                            defined_classes[node.name].append({
                                'file': str(file_path.relative_to(self.directory.parent)),
                                'line': node.lineno,
                                'name': node.name
                            })
                
                # Extract class usage
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name):
                        used_classes.add(node.id)
                    elif isinstance(node, ast.Attribute):
                        used_classes.add(node.attr)
            
            except (SyntaxError, UnicodeDecodeError):
                continue
        
        # Find unused classes
        unused_classes = []
        for class_name, definitions in defined_classes.items():
            if class_name not in used_classes:
                unused_classes.extend(definitions)
        
        return unused_classes
    
    def find_duplicate_code(self, min_lines: int = 5) -> List[Dict[str, any]]:
        """
        Find duplicate code blocks.
        
        Args:
            min_lines: Minimum number of lines to consider as duplicate
        
        Returns:
            List of dicts with file paths and line numbers of duplicates
        """
        # Simple implementation: look for identical function bodies
        function_bodies: Dict[str, List[Dict]] = defaultdict(list)
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                tree = ast.parse(''.join(lines), filename=str(file_path))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Get function body as string
                        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                            start = node.lineno
                            end = node.end_lineno
                            if end - start >= min_lines:
                                body = ''.join(lines[start:end])
                                # Normalize whitespace for comparison
                                normalized = re.sub(r'\s+', ' ', body).strip()
                                
                                function_bodies[normalized].append({
                                    'file': str(file_path.relative_to(self.directory.parent)),
                                    'start_line': start,
                                    'end_line': end,
                                    'function': node.name
                                })
            
            except (SyntaxError, UnicodeDecodeError):
                continue
        
        # Find duplicates
        duplicates = []
        for body, locations in function_bodies.items():
            if len(locations) > 1:
                duplicates.append({
                    'locations': locations,
                    'count': len(locations)
                })
        
        return duplicates
    
    def find_deprecated_api_usage(self) -> List[Dict[str, any]]:
        """
        Find usage of deprecated APIs.
        
        Returns:
            List of dicts with file path, line number, and deprecated API
        """
        # Define deprecated patterns (simpler patterns that match actual usage)
        deprecated_patterns = [
            # Django deprecated APIs
            (r'from\s+django\.conf\.urls\s+import', 'Use django.urls instead'),
            (r'django\.conf\.urls', 'Use django.urls.path or re_path instead'),
            (r'ugettext', 'Use gettext instead'),
            (r'ugettext_lazy', 'Use gettext_lazy instead'),
            (r'render_to_response', 'Use render instead'),
            
            # DRF deprecated APIs
            (r'DEFAULT_AUTHENTICATION_CLASSES.*SessionAuthentication', 
             'Consider using token-based auth'),
            
            # Python deprecated APIs
            (r'from\s+collections\s+import\s+.*Callable', 'Use collections.abc.Callable'),
            (r'from\s+collections\s+import\s+.*Iterable', 'Use collections.abc.Iterable'),
        ]
        
        deprecated_usage = []
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, suggestion in deprecated_patterns:
                        if re.search(pattern, line):
                            deprecated_usage.append({
                                'file': str(file_path.relative_to(self.directory.parent)),
                                'line': line_num,
                                'code': line.strip(),
                                'suggestion': suggestion
                            })
            
            except UnicodeDecodeError:
                continue
        
        return deprecated_usage
    
    def generate_report(self) -> Dict[str, any]:
        """
        Generate a comprehensive cleanup report.
        
        Returns:
            Dict with all analysis results
        """
        return {
            'unused_imports': self.find_unused_imports(),
            'unused_functions': self.find_unused_functions(),
            'unused_classes': self.find_unused_classes(),
            'duplicate_code': self.find_duplicate_code(),
            'deprecated_api': self.find_deprecated_api_usage()
        }
