#!/usr/bin/env python3
"""
CLI for California Eviction Notice Defect Checker

Usage:
    python cli.py analyze <notice_file>
    python cli.py analyze <notice_file> --output report.json
    python cli.py explain <defect_id>
"""

import click
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """California Eviction Notice Defect Checker

    A tool to detect legal defects in eviction notices for California tenants.
    """
    pass


@cli.command()
@click.argument('notice_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON report to file')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed processing information')
def analyze(notice_file: str, output: str, verbose: bool):
    """Analyze an eviction notice for legal defects.

    NOTICE_FILE can be a PDF or image file (PNG, JPG, etc.)
    """
    console.print(f"\n[bold cyan]Analyzing eviction notice:[/bold cyan] {notice_file}\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            # Step 1: OCR
            task1 = progress.add_task("[cyan]Processing document with OCR...", total=None)
            # TODO: Import and call OCR processor
            # from src.ocr.processor import OCRProcessor
            # processor = OCRProcessor()
            # raw_text = processor.process_document(notice_file)
            progress.update(task1, completed=True)

            # Step 2: Extract entities
            task2 = progress.add_task("[cyan]Extracting information with LLM...", total=None)
            # TODO: Import and call entity extractor
            # from src.parser.entity_extractor import EntityExtractor
            # extractor = EntityExtractor()
            # notice = extractor.extract(raw_text)
            progress.update(task2, completed=True)

            # Step 3: Run validators
            task3 = progress.add_task("[cyan]Running defect validators...", total=None)
            # TODO: Import and call validators
            # from src.validators import get_validator
            # validator = get_validator(notice.notice_type)
            # defects = validator.validate(notice)
            progress.update(task3, completed=True)

            # Step 4: LLM edge case analysis
            task4 = progress.add_task("[cyan]Analyzing edge cases with LLM...", total=None)
            # TODO: Import and call LLM analyzer
            # from src.llm.analyzer import LLMAnalyzer
            # analyzer = LLMAnalyzer()
            # additional_defects = analyzer.analyze_edge_cases(notice, defects)
            progress.update(task4, completed=True)

            # Step 5: Generate report
            task5 = progress.add_task("[cyan]Generating report...", total=None)
            # TODO: Import and call report generator
            # from src.reporter.generator import generate_report
            # report = generate_report(notice, defects + additional_defects)
            progress.update(task5, completed=True)

        # Display results (placeholder)
        console.print("\n[yellow]Note: Implementation in progress. This is a placeholder output.[/yellow]\n")

        # TODO: Replace with actual report display
        display_placeholder_report()

        if output:
            # TODO: Save actual report
            with open(output, 'w') as f:
                json.dump({"status": "placeholder"}, f, indent=2)
            console.print(f"\n[green]Report saved to:[/green] {output}\n")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        if verbose:
            console.print_exception()
        raise click.Abort()


@cli.command()
@click.argument('defect_id')
def explain(defect_id: str):
    """Show detailed information about a specific defect.

    DEFECT_ID: The defect code (e.g., 3DP-001)
    """
    console.print(f"\n[bold cyan]Defect Information:[/bold cyan] {defect_id}\n")

    # TODO: Load defect database and display details
    console.print("[yellow]Note: Implementation in progress.[/yellow]\n")


def display_placeholder_report():
    """Display placeholder report for testing"""

    # Summary panel
    summary = Panel(
        "[yellow]Notice Type:[/yellow] 3-Day Notice to Pay Rent or Quit\n"
        "[yellow]Analysis Status:[/yellow] Complete\n"
        "[red]Valid:[/red] ✗ No - Critical defects found",
        title="[bold]Summary[/bold]",
        border_style="cyan"
    )
    console.print(summary)
    console.print()

    # Defects table
    table = Table(title="Defects Found", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Severity", style="magenta", width=12)
    table.add_column("Issue", style="white", width=40)
    table.add_column("Statute", style="yellow", width=30)

    # Placeholder data
    table.add_row(
        "3DP-001",
        "[red]CRITICAL[/red]",
        "Non-rent charges included",
        "CCP § 1161(2)"
    )
    table.add_row(
        "3DP-003",
        "[red]CRITICAL[/red]",
        "No payment address specified",
        "CCP § 1161(2)"
    )
    table.add_row(
        "COM-005",
        "[yellow]MAJOR[/yellow]",
        "Ambiguous payment terms",
        "CCP § 1162"
    )

    console.print(table)
    console.print()

    # Details
    console.print("[bold]Defect Details:[/bold]\n")

    detail1 = Panel(
        "[bold]3DP-001: Non-Rent Charges Included[/bold]\n\n"
        "[yellow]Severity:[/yellow] CRITICAL\n\n"
        "[yellow]Description:[/yellow] The notice includes late fees and utility charges "
        "in addition to rent. A 3-day notice to pay rent can ONLY demand rent, not late fees, "
        "utilities, or other charges.\n\n"
        "[yellow]Legal Basis:[/yellow] CCP § 1161(2); Canal-Randolph v. Pickell (2003)\n\n"
        "[yellow]Tenant Action:[/yellow] This defect likely invalidates the notice. "
        "Landlord must serve a new notice demanding rent only.",
        border_style="red"
    )
    console.print(detail1)
    console.print()


if __name__ == '__main__':
    cli()
