"""CLI package for paper-scanner"""

from typing import Dict

# Map step names to module paths for lazy loading
STEP_REGISTRY_PATHS: Dict[str, str] = {
    "bibtex_import": "paper_scanner.steps.bibtex_import:BibtexImportStep",
    "camo_extraction": "paper_scanner.steps.camo_extraction:CAMOExtractionStep",
    "checkpoint": "paper_scanner.steps.checkpoint:CheckpointStep",
    "citations": "paper_scanner.steps.citations:CitationsStep",
    "decision": "paper_scanner.steps.decision:DecisionStep",
    "deduplication": "paper_scanner.steps.deduplication:DeduplicationStep",
    "download_pdfs": "paper_scanner.steps.download_pdfs:DownloadPDFsStep",
    "echo": "paper_scanner.steps.echo:EchoStep",
    "export": "paper_scanner.steps.export:ExportStep",
    "fix_cite_keys": "paper_scanner.steps.fix_cite_keys:FixCiteKeysStep",
    "generate_embeddings": "paper_scanner.steps.generate_embeddings:GenerateEmbeddingsStep",
    "halt": "paper_scanner.steps.halt:HaltStep",
    "input": "paper_scanner.steps.input:InputStep",
    "journal_screening": "paper_scanner.steps.journal_screening:JournalScreeningStep",
    "keyword_screening": "paper_scanner.steps.keyword_screening:KeywordScreeningStep",
    "llm_classification": "paper_scanner.steps.llm_classification:LLMClassificationStep",
    "metadata_extraction": "paper_scanner.steps.metadata_extraction:MetadataExtractionStep",
    "relevance_filter": "paper_scanner.steps.relevance_filter:RelevanceFilterStep",
    "relevance_scoring": "paper_scanner.steps.relevance_scoring:RelevanceScoringStep",
    "load_files": "paper_scanner.steps.load_files:LoadFilesStep",
    "metadata_screening": "paper_scanner.steps.metadata_screening:MetadataScreeningStep",
    "paper": "paper_scanner.steps.paper:PaperStep",
    "patch": "paper_scanner.steps.patch:PatchStep",
    "report": "paper_scanner.steps.report:ReportStep",
    "retrieve_metadata": "paper_scanner.steps.retrieve_metadata:RetrieveMetadataStep",
    "ris_import": "paper_scanner.steps.ris_import:RisImportStep",
    "rocchio_classifier": "paper_scanner.steps.rocchio_classifier:RocchioClassifierStep",
    "rocchio_screening": "paper_scanner.steps.rocchio_screening:RocchioScreeningStep",
    "run-template": "paper_scanner.steps.run_template:RunTemplateStep",
    "semantic_screening": "paper_scanner.steps.semantic_screening:SemanticScreeningStep",
    "upload_database": "paper_scanner.steps.upload_database:UploadDatabaseStep",
}

__all__ = ["STEP_REGISTRY_PATHS"]
