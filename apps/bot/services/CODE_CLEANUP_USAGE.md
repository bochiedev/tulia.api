# Code Cleanup Analyzer Usage Guide

## Overview

The Code Cleanup Analyzer is a tool for identifying code quality issues in Python codebases, including:
- Unused imports
- Unused functions and classes
- Duplicate code blocks
- Deprecated API usage

## Basic Usage

```python
from apps.bot.services.code_cleanup_analyzer import CodeCleanupAnalyzer

# Analyze a directory
analyzer = CodeCleanupAnalyzer('apps/bot')

# Generate comprehensive report
report = analyzer.generate_report()

# Access specific findings
unused_imports = report['unused_imports']
unused_functions = report['unused_functions']
unused_classes = report['unused_classes']
duplicate_code = report['duplicate_code']
deprecated_api = report['deprecated_api']
```

## Individual Analysis Methods

### Find Unused Imports
```python
analyzer = CodeCleanupAnalyzer('apps/bot')
unused = analyzer.find_unused_imports()

for item in unused:
    print(f"{item['file']}:{item['line']} - Unused import: {item['import']}")
```

### Find Unused Functions
```python
analyzer = CodeCleanupAnalyzer('apps/bot')
unused = analyzer.find_unused_functions()

for item in unused:
    print(f"{item['file']}:{item['line']} - Unused function: {item['name']}")
```

### Find Unused Classes
```python
analyzer = CodeCleanupAnalyzer('apps/bot')
unused = analyzer.find_unused_classes()

for item in unused:
    print(f"{item['file']}:{item['line']} - Unused class: {item['name']}")
```

### Find Duplicate Code
```python
analyzer = CodeCleanupAnalyzer('apps/bot')
duplicates = analyzer.find_duplicate_code(min_lines=5)

for dup in duplicates:
    print(f"Found {dup['count']} duplicates:")
    for loc in dup['locations']:
        print(f"  {loc['file']}:{loc['start_line']}-{loc['end_line']} in {loc['function']}")
```

### Find Deprecated API Usage
```python
analyzer = CodeCleanupAnalyzer('apps/bot')
deprecated = analyzer.find_deprecated_api_usage()

for item in deprecated:
    print(f"{item['file']}:{item['line']} - {item['code']}")
    print(f"  Suggestion: {item['suggestion']}")
```

## Analyzing a Single File

```python
analyzer = CodeCleanupAnalyzer('apps/bot/services/ai_agent_service.py')
report = analyzer.generate_report()
```

## Example: Cleanup Script

```python
#!/usr/bin/env python
"""
Script to analyze codebase and generate cleanup report.
"""
from apps.bot.services.code_cleanup_analyzer import CodeCleanupAnalyzer
import json

def main():
    # Analyze the bot app
    analyzer = CodeCleanupAnalyzer('apps/bot')
    report = analyzer.generate_report()
    
    # Print summary
    print("Code Cleanup Report")
    print("=" * 50)
    print(f"Unused imports: {len(report['unused_imports'])}")
    print(f"Unused functions: {len(report['unused_functions'])}")
    print(f"Unused classes: {len(report['unused_classes'])}")
    print(f"Duplicate code blocks: {len(report['duplicate_code'])}")
    print(f"Deprecated API usage: {len(report['deprecated_api'])}")
    
    # Save detailed report
    with open('cleanup_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\nDetailed report saved to cleanup_report.json")

if __name__ == '__main__':
    main()
```

## Notes

- Private functions and classes (starting with `_`) are not flagged as unused
- The analyzer gracefully handles files with syntax errors
- Wildcard imports (`from module import *`) are skipped
- Duplicate detection requires functions to be at least 5 lines by default
- The analyzer uses AST parsing for accurate code analysis

## Detected Deprecated APIs

The analyzer currently detects:
- `django.conf.urls` (use `django.urls` instead)
- `ugettext` / `ugettext_lazy` (use `gettext` / `gettext_lazy`)
- `render_to_response` (use `render`)
- `collections.Callable` / `collections.Iterable` (use `collections.abc`)

## Limitations

- Cross-module usage detection is limited to the analyzed directory
- Dynamic imports and introspection may cause false positives
- Duplicate detection is based on normalized function bodies
- Some deprecated APIs may not be detected if patterns are not defined
