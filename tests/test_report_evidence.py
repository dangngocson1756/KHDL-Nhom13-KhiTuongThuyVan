"""Regression checks for source contracts and held-out report diagnostics."""
import sys,json,copy,unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from real_weather import validate_source_payload

class EvidenceChecks(unittest.TestCase):
 def setUp(self):
  self.body=(ROOT/'data/era5/Ha_Noi.json').read_bytes()
  self.obj=json.loads(self.body)
  self.meta=json.loads((ROOT/'data/era5/Ha_Noi_request.json').read_text())
 def test_modified_cache_is_rejected(self):
  validate_source_payload(self.obj,self.meta,self.body)
  with self.assertRaisesRegex(ValueError,'SHA-256'):validate_source_payload(self.obj,self.meta,self.body+b' ')
 def test_model_units_and_calendar_contracts(self):
  m=copy.deepcopy(self.meta);m['parameters']['models']='best_match'
  with self.assertRaisesRegex(ValueError,'model/timezone'):validate_source_payload(self.obj,m,self.body)
  o=copy.deepcopy(self.obj);o['daily_units']['wind_speed_10m_mean']='km/h'
  with self.assertRaisesRegex(ValueError,'unit'):validate_source_payload(o,self.meta,self.body)
  o=copy.deepcopy(self.obj);o['daily']['time'][2]=o['daily']['time'][1]
  with self.assertRaisesRegex(ValueError,'calendar'):validate_source_payload(o,self.meta,self.body)
 def test_confusion_and_calibration_conserve_test_samples(self):
  p=pd.read_csv(ROOT/'outputs/real/predictions.csv');d=pd.read_csv(ROOT/'outputs/report_evidence/rain_confusion.csv')
  allrow=d[d.location.eq('ALL')].iloc[0]
  self.assertEqual(int(allrow[['TP','FP','FN','TN']].sum()),len(p))
  self.assertEqual(int(d[d.location.ne('ALL')].n.sum()),len(p))
  bins=pd.read_csv(ROOT/'outputs/report_evidence/calibration.csv')
  self.assertEqual(int(bins.n.sum()),len(p))
  self.assertAlmostEqual(float((bins.n*bins.observed_rate).sum()),int(p.target_rain.ge(1).sum()),places=8)
 def test_extreme_error_and_sql_totals_recomputed(self):
  p=pd.read_csv(ROOT/'outputs/real/predictions.csv');e=pd.read_csv(ROOT/'outputs/report_evidence/largest_errors.csv')
  self.assertAlmostEqual(float(e.abs_error.max()),float((p.R3-p.target_temp).abs().max()),places=10)
  d=pd.read_csv(ROOT/'outputs/real/clean.csv');q=pd.read_csv(ROOT/'outputs/report_evidence/sql_era5_totals.csv')
  for x in q.itertuples():
   g=d[d.location.eq(x.location)];self.assertEqual(len(g),x.n);self.assertAlmostEqual(g.rain.sum(),x.rain_sum_mm,places=5)
if __name__=='__main__':unittest.main()
