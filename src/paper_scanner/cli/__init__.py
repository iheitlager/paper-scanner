"""CLI package for paper-scanner"""

from typing import Dict

# Map step names to module paths for lazy loading
STEP_REGISTRY_PATHS: Dict[str, str] = {
    "bibtex_import": "paper_scanner.steps.bibtex_import:BibtexImportStep",
    "categorization": "paper_scanner.steps.categorization:CategorizationStep",
    "checkpoint": "paper_scanner.steps.checkpoint:CheckpointStep",
    "deduplication": "paper_scanner.steps.deduplication:DeduplicationStep",
    "download_pdfs": "paper_scanner.steps.download_pdfs:DownloadPDFsStep",
    "dump_db": "paper_scanner.steps.dump_db:DumpDbStep",
    "echo": "paper_scanner.steps.echo:EchoStep",
    "export": "paper_scanner.steps.export:ExportStep",
    "halt": "paper_scanner.steps.halt:HaltStep",
    "paper": "paper_scanner.steps.paper:PaperStep",
    "input": "paper_scanner.steps.input:InputStep",
    "keyword_screening": "paper_scanner.steps.keyword_screening:KeywordScreeningStep",
    "load_files": "paper_scanner.steps.load_files:LoadFilesStep",
    "patch": "paper_scanner.steps.patch:PatchStep",
    "retrieve_metadata": "paper_scanner.steps.retrieve_metadata:RetrieveMetadataStep",
    "run-template": "paper_scanner.steps.run_template:RunTemplateStep",
    "semantic_screening": "paper_scanner.steps.semantic_screening:SemanticScreeningStep",
    "summarize": "paper_scanner.steps.summarize:SummarizeStep",
    "citations": "paper_scanner.steps.citations:CitationsStep",
    "upload_database": "paper_scanner.steps.upload_database:UploadDatabaseStep",
}

__all__ = ["STEP_REGISTRY_PATHS"]
