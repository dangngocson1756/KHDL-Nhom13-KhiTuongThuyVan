"""Remove inherited application properties from the report/template OOXML package."""
from __future__ import annotations
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED

APP_XML = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>python-docx</Application><Company>Nhom 13 - PTIT</Company></Properties>'''


def clean_application_properties(path: Path) -> None:
    """Drop stale TitlesOfParts, HeadingPairs, company and other cached template fields."""
    with NamedTemporaryFile(dir=path.parent, suffix='.docx', delete=False) as f:
        tmp = Path(f.name)
    try:
        with ZipFile(path) as src, ZipFile(tmp, 'w', ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = APP_XML if item.filename == 'docProps/app.xml' else src.read(item.filename)
                dst.writestr(item, data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
