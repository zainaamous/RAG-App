"""
Enhanced Command Line Interface for RAG System
Provides easy management of indexing, querying, and system operations
"""
import click
import json
import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax

from config import config, config_manager, ConfigManager
from logger import logger, log_operation
from indexer import EnhancedIndexer, IndexingStats
from query_engine import EnhancedQueryEngine, QueryResult
from filesys import iter_files

console = Console()

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
def cli(verbose: bool, config_path: Optional[str]):
    """Enhanced RAG System CLI"""
    if verbose:
        logger.logger.setLevel("DEBUG")
    
    if config_path:
        global config_manager
        config_manager = ConfigManager(config_path)
    
    console.print(Panel.fit(
        "[bold blue]🚀 Enhanced RAG System CLI[/bold blue]\n"
        f"Namespace: [green]{config.rag_namespace}[/green]\n"
        f"Index: [green]{config.pinecone.index_name}[/green]",
        title="System Info"
    ))

@cli.command()
@click.argument('paths', nargs=-1, required=True)
@click.option('--namespace', '-n', help='Pinecone namespace')
@click.option('--wipe', is_flag=True, help='Clear namespace before indexing')
@click.option('--reindex', is_flag=True, help='Reindex existing documents')
@click.option('--workers', '-w', default=4, help='Number of parallel workers')
@click.option('--dry-run', is_flag=True, help='Show what would be indexed without actually doing it')
def index(paths: List[str], namespace: str, wipe: bool, reindex: bool, workers: int, dry_run: bool):
    """Index documents into the knowledge base"""
    namespace = namespace or config.rag_namespace
    
    console.print(f"\n[bold]📚 Indexing Documents[/bold]")
    console.print(f"Paths: {', '.join(paths)}")
    console.print(f"Namespace: [green]{namespace}[/green]")
    
    if dry_run:
        console.print("\n[yellow]🔍 Dry Run Mode - Finding files...[/yellow]")
        files = iter_files(list(paths))
        
        if not files:
            console.print("[red]❌ No supported files found[/red]")
            return
        
        table = Table(title="Files to be Indexed")
        table.add_column("File Path", style="cyan")
        table.add_column("Type", style="magenta")
        
        for file_path in files:
            file_type = Path(file_path).suffix
            table.add_row(file_path, file_type)
        
        console.print(table)
        console.print(f"\n[green]✅ Found {len(files)} files to index[/green]")
        return
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing indexer...", total=None)
            
            indexer = EnhancedIndexer(namespace)
            progress.update(task, description="Indexing documents...")
            
            stats = indexer.index_paths(
                list(paths), 
                wipe=wipe, 
                reindex=reindex, 
                max_workers=workers
            )
        
        # Display results
        _display_indexing_results(stats)
        
    except Exception as e:
        console.print(f"[red]❌ Indexing failed: {str(e)}[/red]")
        logger.error(f"CLI indexing failed: {e}")
        sys.exit(1)

@cli.command()
@click.argument('question', required=True)
@click.option('--namespace', '-n', help='Pinecone namespace')
@click.option('--format', '-f', type=click.Choice(['text', 'json', 'detailed']), default='text', help='Output format')
def query(question: str, namespace: str, format: str):
    """Query the knowledge base"""
    namespace = namespace or config.rag_namespace
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing query...", total=None)
            
            engine = EnhancedQueryEngine(namespace)
            result = engine.query(question)
        
        # Display results based on format
        if format == 'json':
            console.print(json.dumps({
                "answer": result.answer,
                "sources": result.sources,
                "confidence": result.confidence,
                "query_type": result.query_type.value,
                "processing_time": result.processing_time
            }, indent=2))
        elif format == 'detailed':
            _display_detailed_query_result(result)
        else:
            _display_simple_query_result(result)
            
    except Exception as e:
        console.print(f"[red]❌ Query failed: {str(e)}[/red]")
        logger.error(f"CLI query failed: {e}")
        sys.exit(1)

@cli.command()
@click.option('--namespace', '-n', help='Pinecone namespace')
def stats(namespace: str):
    """Show system statistics"""
    namespace = namespace or config.rag_namespace
    
    try:
        indexer = EnhancedIndexer(namespace)
        stats = indexer.get_namespace_stats()
        
        table = Table(title=f"System Statistics - {namespace}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in stats.items():
            if key != "error":
                table.add_row(key.replace("_", " ").title(), str(value))
        
        console.print(table)
        
        if "error" in stats:
            console.print(f"[red]❌ Error: {stats['error']}[/red]")
            
    except Exception as e:
        console.print(f"[red]❌ Failed to get stats: {str(e)}[/red]")

@cli.command()
@click.option('--namespace', '-n', help='Pinecone namespace')
@click.option('--limit', '-l', default=20, help='Maximum number of documents to show')
def list_docs(namespace: str, limit: int):
    """List indexed documents"""
    namespace = namespace or config.rag_namespace
    
    try:
        indexer = EnhancedIndexer(namespace)
        documents = indexer.list_documents(limit)
        
        if not documents:
            console.print("[yellow]📭 No documents found in namespace[/yellow]")
            return
        
        table = Table(title=f"Indexed Documents - {namespace}")
        table.add_column("Document ID", style="cyan")
        table.add_column("Source", style="magenta")
        table.add_column("Chunks", style="green")
        table.add_column("Version", style="yellow")
        
        for doc in documents:
            table.add_row(
                doc["doc_uid"][:12] + "...",
                Path(doc["source"]).name if doc["source"] != "unknown" else "unknown",
                str(doc["chunk_count"]),
                doc.get("version", "1.0")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]❌ Failed to list documents: {str(e)}[/red]")

@cli.command()
@click.argument('doc_id')
@click.option('--namespace', '-n', help='Pinecone namespace')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def delete_doc(doc_id: str, namespace: str, confirm: bool):
    """Delete a document from the knowledge base"""
    namespace = namespace or config.rag_namespace
    
    if not confirm:
        if not Confirm.ask(f"Delete document {doc_id} from namespace {namespace}?"):
            console.print("[yellow]❌ Operation cancelled[/yellow]")
            return
    
    try:
        indexer = EnhancedIndexer(namespace)
        indexer._delete_document(doc_id)
        console.print(f"[green]✅ Document {doc_id} deleted successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to delete document: {str(e)}[/red]")

@cli.command()
def config_show():
    """Show current configuration"""
    config_dict = {
        "API Keys": {
            "Google API Key": "***" if config.google_api_key else "Not set",
            "Pinecone API Key": "***" if config.pinecone_api_key else "Not set"
        },
        "Core Settings": {
            "Namespace": config.rag_namespace,
            "Index Name": config.pinecone.index_name,
            "Doc ID Mode": config.doc_id_hash_mode
        },
        "Chunking": {
            "Chunk Size": config.chunking.chunk_size,
            "Chunk Overlap": config.chunking.chunk_overlap
        },
        "Retrieval": {
            "Max Docs": config.retrieval.max_docs,
            "K Per Doc": config.retrieval.k_per_doc,
            "Similarity Threshold": config.retrieval.similarity_threshold
        },
        "LLM": {
            "Model": config.llm.model,
            "Temperature": config.llm.temperature,
            "Max Tokens": config.llm.max_tokens
        }
    }
    
    for section, settings in config_dict.items():
        table = Table(title=section)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in settings.items():
            table.add_row(key, str(value))
        
        console.print(table)
        console.print()

@cli.command()
@click.argument('key')
@click.argument('value')
def config_set(key: str, value: str):
    """Set a configuration value"""
    try:
        # Handle nested keys like "chunking.chunk_size"
        if "." in key:
            section, setting = key.split(".", 1)
            if hasattr(config, section):
                section_obj = getattr(config, section)
                if hasattr(section_obj, setting):
                    # Convert value to appropriate type
                    current_value = getattr(section_obj, setting)
                    if isinstance(current_value, bool):
                        new_value = value.lower() in ('true', '1', 'yes', 'on')
                    elif isinstance(current_value, int):
                        new_value = int(value)
                    elif isinstance(current_value, float):
                        new_value = float(value)
                    else:
                        new_value = value
                    
                    setattr(section_obj, setting, new_value)
                    console.print(f"[green]✅ Set {key} = {new_value}[/green]")
                else:
                    console.print(f"[red]❌ Setting '{setting}' not found in section '{section}'[/red]")
            else:
                console.print(f"[red]❌ Section '{section}' not found[/red]")
        else:
            # Handle top-level keys
            if hasattr(config, key):
                setattr(config, key, value)
                console.print(f"[green]✅ Set {key} = {value}[/green]")
            else:
                console.print(f"[red]❌ Configuration key '{key}' not found[/red]")
                
    except ValueError as e:
        console.print(f"[red]❌ Invalid value for {key}: {str(e)}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Failed to set configuration: {str(e)}[/red]")

@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def config_save(output: Optional[str]):
    """Save current configuration to file"""
    try:
        output_file = output or "rag_config.yaml"
        config_manager.save_config(output_file)
        console.print(f"[green]✅ Configuration saved to {output_file}[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to save configuration: {str(e)}[/red]")

@cli.command()
@click.option('--port', '-p', default=8000, help='API server port')
@click.option('--host', '-h', default='0.0.0.0', help='API server host')
def serve(port: int, host: str):
    """Start the API server"""
    try:
        import uvicorn
        from api import app
        
        console.print(f"[green]🚀 Starting API server on {host}:{port}[/green]")
        console.print(f"[blue]📖 API docs: http://{host}:{port}/docs[/blue]")
        
        uvicorn.run(app, host=host, port=port, log_level="info")
        
    except ImportError:
        console.print("[red]❌ FastAPI not installed. Run: pip install fastapi uvicorn[/red]")
    except Exception as e:
        console.print(f"[red]❌ Failed to start server: {str(e)}[/red]")

def _display_indexing_results(stats: IndexingStats):
    """Display indexing results in a formatted table"""
    table = Table(title="Indexing Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Files", str(stats.total_files))
    table.add_row("Successful", str(stats.successful))
    table.add_row("Failed", str(stats.failed))
    table.add_row("Skipped", str(stats.skipped))
    table.add_row("Total Chunks", str(stats.total_chunks))
    table.add_row("Duration", f"{stats.duration:.2f}s")
    
    console.print(table)
    
    if stats.errors:
        console.print("\n[red]❌ Errors:[/red]")
        for error in stats.errors:
            console.print(f"  • {error}")

def _display_simple_query_result(result: QueryResult):
    """Display query result in simple format"""
    console.print(f"\n[bold green]Answer:[/bold green]")
    console.print(result.answer)
    
    if result.sources:
        console.print(f"\n[bold blue]Sources ({len(result.sources)}):[/bold blue]")
        for i, source in enumerate(result.sources, 1):
            console.print(f"  {i}. {source['source']}")

def _display_detailed_query_result(result: QueryResult):
    """Display query result in detailed format"""
    # Answer
    console.print(Panel(result.answer, title="[bold green]Answer[/bold green]"))
    
    # Metadata
    metadata_table = Table(title="Query Metadata")
    metadata_table.add_column("Metric", style="cyan")
    metadata_table.add_column("Value", style="green")
    
    metadata_table.add_row("Query Type", result.query_type.value)
    metadata_table.add_row("Confidence", f"{result.confidence:.2f}")
    metadata_table.add_row("Processing Time", f"{result.processing_time:.2f}s")
    metadata_table.add_row("Chunks Retrieved", str(result.total_chunks_retrieved))
    metadata_table.add_row("Chunks Used", str(result.relevant_chunks_used))
    
    console.print(metadata_table)
    
    # Sources
    if result.sources:
        console.print(f"\n[bold blue]Sources ({len(result.sources)}):[/bold blue]")
        for i, source in enumerate(result.sources, 1):
            console.print(f"\n[cyan]{i}. {source['source']}[/cyan]")
            console.print(f"   Doc ID: {source['doc_uid']}")
            console.print(f"   Preview: {source['content_preview']}")

if __name__ == "__main__":
    cli()
