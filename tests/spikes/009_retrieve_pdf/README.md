

**PDFInfo** - PDF download tracking:
```python
class PDFInfo(BaseModel):
    file_path: Optional[str]
    download_source: Optional[str]  # "unpaywall", "openalex", "arxiv"
    download_url: Optional[str]
    downloaded_at: Optional[datetime]
```


### Step 5: get_pdf
```
Paper(selected, if file_path not set) → Search for PDFs → Download
Output: Paper(with pdf_info, oa_status filled)
```
