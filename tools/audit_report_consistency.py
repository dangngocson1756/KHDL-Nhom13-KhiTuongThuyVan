"""Audit the ERA5-first report, external-source SQLite, scores, provenance and metadata."""
from pathlib import Path
import hashlib,json,re,sqlite3,sys,zipfile
import numpy as np
import pandas as pd
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from report_extended import tables,figures,vn

def main():
 a=json.loads((ROOT/'outputs/analysis.json').read_text());s=json.loads((ROOT/'outputs/real/summary.json').read_text())
 src=(ROOT/'docs/report_src/noi_dung.md').read_text();ts=tables(a);fs=figures()
 assert set(re.findall(r'^@table (\S+)',src,re.M))==set(ts)
 assert set(re.findall(r'^@figure (\S+)',src,re.M))==set(fs)
 # There must be no benchmark table/figure in the main research-result chapter.
 c5=src.split('# Chương 5',1)[1].split('# Chương 6',1)[0]
 assert 'benchmark_qc' not in c5 and 'benchmark_limits' not in c5
 c6=src.split('# Chương 6',1)[1].split('@appendix',1)[0]
 assert all(f'Q{i} —' in c6 for i in range(1,5))
 assert '−0,0928' not in c6 and '0,2366' not in c6
 f=pd.read_csv(ROOT/'outputs/real/features.csv');p=pd.read_csv(ROOT/'outputs/real/predictions.csv');yt=(p.target_rain>=1).astype(float)
 prior=(f.loc[f.split.eq('train'),'target_rain']>=1).mean();ref=((yt-prior)**2).mean();bs=((yt-p.rain_probability)**2).mean()
 assert np.isclose(s['rain']['BSS_train_climatology'],1-bs/ref)
 assert vn(s['rain']['BSS_train_climatology'],4) in src
 with sqlite3.connect(ROOT/'outputs/kttv_weather.sqlite') as c:
  assert c.execute('SELECT COUNT(*) FROM era5_daily').fetchone()[0]==9861
  assert c.execute('SELECT COUNT(*) FROM hydrology_daily').fetchone()[0]==5478
  j=json.loads((ROOT/'data/era5/Ha_Noi.json').read_text())['daily'];i=j['time'].index('2024-09-07')
  actual=c.execute("SELECT rain_mm,pressure_msl_hpa,wind_ms FROM era5_daily WHERE location='Ha_Noi' AND date='2024-09-07'").fetchone()
  np.testing.assert_allclose(actual,[j[k][i] for k in ['precipitation_sum','pressure_msl_mean','wind_speed_10m_mean']])
 for m in (ROOT/'data/hydrology').glob('*_request.json'):
  j=json.loads(m.read_text());raw=m.with_name(m.name.replace('_request',''))
  assert hashlib.sha256(raw.read_bytes()).hexdigest()==j['sha256']
 for name in ['kttv_metadata.json','kttv_file_manifest.json']:
  m=json.loads((ROOT/'data/raw'/name).read_text());assert m['dataset_nature']=='synthetic_fault_injected_benchmark';assert m['reproducibility']['original_generator_included'] is False
 bad=('bất động sản','giá rao','Văn Đạt','Yến Nhi','Như Quỳnh','Đề tài số 3','STT 34')
 for path in [ROOT/'docs/BAO_CAO_TIEU_LUAN_6_CHUONG.docx',ROOT/'docs/report_assets/ptit_cover_template.docx']:
  with zipfile.ZipFile(path) as z:
   for n in z.namelist():
    if n.endswith('.xml'):
     text=z.read(n).decode(errors='replace');assert not any(b.casefold() in text.casefold() for b in bad),(path,n)
 pdf=PdfReader(str(ROOT/'docs/BAO_CAO_TIEU_LUAN_6_CHUONG.pdf'));pt='\n'.join(pg.extract_text() or '' for pg in pdf.pages)
 assert not any(b.casefold() in str(pdf.metadata).casefold() for b in bad)
 assert '[[table:' not in pt and '[[figure:' not in pt
 for token in ['1.670,1','147,9','196,6','5.478','0,3810']:
  assert token in pt,token
 for i in range(1,len(ts)+1):assert f'Bảng {i}:' in pt
 for i in range(1,len(fs)+1):assert f'Hình {i}:' in pt
 print(f'Report audit PASSED: {len(ts)} tables, {len(fs)} figures; ERA5-first chapter, Q1–Q4, BSS, GloFAS hashes, SQLite, Yagi, corrected QCVN reference and metadata.')
if __name__=='__main__':main()
