"""
Management command to run security audit for AI agent system.

Usage:
    python manage.py run_security_audit
    python manage.py run_security_audit --verbose
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import json

from apps.bot.security_audit import run_security_audit


class Command(BaseCommand):
    help = 'Run security audit for AI agent multi-tenant isolation and data protection'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed audit results',
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output results to JSON file',
        )
    
    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        output_file = options.get('output')
        
        self.stdout.write(self.style.WARNING('Starting security audit...'))
        self.stdout.write('')
        
        # Run audit
        results = run_security_audit()
        
        # Display results
        self.stdout.write(self.style.SUCCESS(f"Audit completed at {results['timestamp']}"))
        self.stdout.write('')
        
        # Overall status
        if results['overall_status'] == 'PASSED':
            self.stdout.write(self.style.SUCCESS(f"✓ Overall Status: {results['overall_status']}"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Overall Status: {results['overall_status']}"))
        
        self.stdout.write('')
        
        # Tenant isolation results
        isolation = results['tenant_isolation']
        self.stdout.write(self.style.WARNING('Tenant Isolation Audit:'))
        self.stdout.write(f"  Models checked: {isolation['models_checked']}")
        self.stdout.write(f"  Issues found: {len(isolation['issues_found'])}")
        self.stdout.write(f"  Recommendations: {len(isolation.get('recommendations', []))}")
        self.stdout.write('')
        
        # Critical issues
        if results['critical_issues']:
            self.stdout.write(self.style.ERROR('CRITICAL ISSUES:'))
            for issue in results['critical_issues']:
                self.stdout.write(self.style.ERROR(f"  ✗ {issue['model']}: {issue['issue']}"))
                self.stdout.write(f"    Recommendation: {issue['recommendation']}")
            self.stdout.write('')
        
        # Warnings
        if results['warnings']:
            self.stdout.write(self.style.WARNING('WARNINGS:'))
            for warning in results['warnings']:
                self.stdout.write(self.style.WARNING(f"  ! {warning['model']}: {warning['issue']}"))
                self.stdout.write(f"    Recommendation: {warning['recommendation']}")
            self.stdout.write('')
        
        # Recommendations
        if results['recommendations'] and verbose:
            self.stdout.write(self.style.NOTICE('RECOMMENDATIONS:'))
            for rec in results['recommendations']:
                self.stdout.write(f"  → {rec['model']}: {rec['recommendation']}")
            self.stdout.write('')
        
        # Detailed results in verbose mode
        if verbose:
            self.stdout.write(self.style.NOTICE('Detailed Results:'))
            
            # Tenant isolation details
            if isolation['issues_found']:
                self.stdout.write('  Tenant Isolation Issues:')
                for issue in isolation['issues_found']:
                    self.stdout.write(f"    - [{issue['severity']}] {issue['model']}")
                    self.stdout.write(f"      Issue: {issue['issue']}")
                    self.stdout.write(f"      Fix: {issue['recommendation']}")
                self.stdout.write('')
        
        # Save to file if requested
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                self.stdout.write(self.style.SUCCESS(f"Results saved to {output_file}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to save results: {e}"))
        
        # Exit with error code if audit failed
        if results['overall_status'] != 'PASSED':
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Security audit FAILED. Please address the issues above.'))
            exit(1)
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Security audit PASSED. All checks completed successfully.'))
