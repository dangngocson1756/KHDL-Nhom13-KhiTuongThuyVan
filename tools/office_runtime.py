"""Portable LibreOffice discovery and isolated profile for document conversion."""
from pathlib import Path
import os,shutil,subprocess,tempfile

def find_office():
 candidates=[os.environ.get('LIBREOFFICE_BIN'),shutil.which('soffice'),shutil.which('libreoffice')]
 for env in ['ProgramFiles','ProgramFiles(x86)']:
  candidates.append(str(Path(os.environ.get(env,'C:/Program Files'))/'LibreOffice/program/soffice.exe'))
 candidates.append('/Applications/LibreOffice.app/Contents/MacOS/soffice')
 runtime=os.environ.get('CODEX_PRIMARY_RUNTIME_ROOT')
 if runtime:candidates.append(str(Path(runtime)/'dependencies/bin/override/soffice'))
 return next((str(p) for p in candidates if p and Path(p).is_file()),None)

def convert_document(source,outdir,format):
 executable=find_office()
 if executable is None:raise RuntimeError('Cần cài LibreOffice hoặc đặt LIBREOFFICE_BIN tới soffice.exe để xuất PDF/tính lại Excel.')
 with tempfile.TemporaryDirectory(prefix='nhom13_office_') as profile:
  subprocess.run([executable,'-env:UserInstallation='+Path(profile).resolve().as_uri(),'--headless','--convert-to',format,'--outdir',str(outdir),str(source)],check=True)
