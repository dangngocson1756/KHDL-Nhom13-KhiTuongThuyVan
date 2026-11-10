"""Source integrity, scoring and database checks for the ERA5-first study."""
import hashlib,json,sqlite3,unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
class StudyAdditions(unittest.TestCase):
 def test_hydrology_integrity_units_dates(self):
  for p in (ROOT/'data/hydrology').glob('*_request.json'):
   m=json.loads(p.read_text());raw=p.with_name(p.name.replace('_request',''))
   self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),m['sha256'])
   j=json.loads(raw.read_text());self.assertEqual(j['daily_units']['river_discharge'],'m³/s');self.assertEqual(j['utc_offset_seconds'],0)
   self.assertEqual(m['params']['models'],'consolidated_v4')
  d=pd.read_csv(ROOT/'outputs/hydrology/daily.csv',parse_dates=['date'])
  self.assertEqual(len(d),5478);self.assertFalse(d.duplicated(['location','date']).any());self.assertTrue(d.river_discharge_m3s.ge(0).all())
  self.assertEqual(str(d.date.min().date()),'2017-01-01');self.assertEqual(str(d.date.max().date()),'2021-12-31')
 def test_rain_skill_uses_train_reference(self):
  f=pd.read_csv(ROOT/'outputs/real/features.csv');p=pd.read_csv(ROOT/'outputs/real/predictions.csv');j=json.loads((ROOT/'outputs/real/summary.json').read_text())['rain']
  prior=(f.loc[f.split.eq('train'),'target_rain']>=1).mean();y=(p.target_rain>=1).astype(float)
  bs=np.mean((y-p.rain_probability)**2);ref=np.mean((y-prior)**2)
  self.assertAlmostEqual(j['BSS_train_climatology'],1-bs/ref,places=12)
  self.assertAlmostEqual(j['Brier_climatology_train'],ref,places=12)
  self.assertAlmostEqual(j['train_prevalence'],prior,places=12)
 def test_real_calendar_groups_and_clustering(self):
  d=pd.read_csv(ROOT/'outputs/real/location_season.csv')
  self.assertEqual(set(d.season),{'Tháng 12–2','Tháng 3–4','Tháng 5–8','Tháng 9–11'})
  t=pd.read_csv(ROOT/'outputs/real/cluster_trials.csv');self.assertEqual(list(t.k),[2,3,4,5]);self.assertTrue(t.silhouette_sample.between(-1,1).all())
 def test_real_database_matches_source(self):
  with sqlite3.connect(ROOT/'outputs/kttv_weather.sqlite') as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM era5_daily').fetchone()[0],9861)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM hydrology_daily').fetchone()[0],5478)
   x=c.execute("SELECT rain_mm, pressure_msl_hpa, wind_ms FROM era5_daily WHERE location='Ha_Noi' AND date='2024-09-07'").fetchone()
   np.testing.assert_allclose(x,[196.6,993.2,8.16])
   src=pd.read_csv(ROOT/'outputs/real/clean.csv');h=pd.read_csv(ROOT/'outputs/hydrology/daily.csv')
   self.assertAlmostEqual(c.execute('SELECT SUM(rain_mm) FROM era5_daily').fetchone()[0],src.rain.sum(),places=6)
   self.assertAlmostEqual(c.execute('SELECT SUM(river_discharge_m3s) FROM hydrology_daily').fetchone()[0],h.river_discharge_m3s.sum(),places=6)
 def test_split_policies_are_explicit(self):
  r=pd.read_csv(ROOT/'outputs/real/features.csv',parse_dates=['date','target_date'])
  self.assertEqual(len(r),9855)
  self.assertEqual(int((r.date.dt.year!=r.target_date.dt.year).sum()),24) # eight year boundaries x 3 grids, including within train
  self.assertTrue(r.loc[r.split.eq('validation'),'target_date'].dt.year.eq(2024).all())
  syn=pd.read_csv(ROOT/'data/processed/weather_clean.csv')
  self.assertEqual(json.loads((ROOT/'outputs/analysis.json').read_text())['counts']['clean_count'],len(syn))
if __name__=='__main__':unittest.main()
