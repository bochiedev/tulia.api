#!/usr/bin/env python3
"""
Script to fix LLMRouter async context issues across all files.
"""

import os
import re

# Files to fix
files_to_fix = [
    'apps/bot/langgraph/llm_nodes.py',
    'apps/bot/langgraph/offers_journey.py',
    'apps/bot/langgraph/payment_nodes.py',
    'apps/bot/langgraph/support_journey.py',
    'apps/bot/langgraph/sales_journey.py',
    'apps/bot/langgraph/preferences_journey.py',
    'apps/bot/langgraph/orders_journey.py',
    'apps/bot/langgraph/sales_journey_nodes.py',
]

def fix_file(filepath):
    """Fix LLMRouter usage in a file."""
    print(f"Fixing {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern to match: llm_router = LLMRouter(tenant)
    # Replace with: llm_router = LLMRouter(tenant)\n            await llm_router._ensure_config_loaded()
    pattern = r'(\s+)llm_router = LLMRouter\(tenant\)'
    replacement = r'\1llm_router = LLMRouter(tenant)\n\1await llm_router._ensure_config_loaded()'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"  ✅ Fixed {filepath}")
    else:
        print(f"  ⚠️  No changes needed in {filepath}")

def main():
    """Main function."""
    print("🔧 Fixing LLMRouter async context issues...")
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_file(file_path)
        else:
            print(f"  ❌ File not found: {file_path}")
    
    print("✅ All files processed!")

if __name__ == "__main__":
    main()