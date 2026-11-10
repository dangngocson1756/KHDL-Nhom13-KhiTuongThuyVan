"""Acquire and replay pinned GloFAS v4 consolidated daily discharge, UTC, 2017–2021.
This is model output, not river-gauge observations; it is not a weather predictor.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json,urllib.parse,urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/hydrology';OUT=ROOT/'outputs/hydrology'
POINTS={'Ha_Noi':(21.02,105.80),'Da_Nang':(16.04,108.20),'TP_HCM':(10.82,106.67)}
PARAMS={'start_date':'2017-01-01','end_date':'2021-12-31','daily':'river_discharge','models':'consolidated_v4','timezone':'GMT','cell_selection':'nearest'}

def run(refresh=False):
 RAW.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 frames=[];provenance=[];summary=[]
 for name,(lat,lon) in POINTS.items():
  path=RAW/f'{name}.json';request_path=RAW/f'{name}_request.json'
  params={**PARAMS,'latitude':lat,'longitude':lon}
  url='https://flood-api.open-meteo.com/v1/flood?'+urllib.parse.urlencode(params)
  if refresh or not path.exists():
   req=urllib.request.Request(url,headers={'User-Agent':'PTIT-Nhom13-academic/1.0'})
   with urllib.request.urlopen(req,timeout=40) as resp:body=resp.read()
   payload=json.loads(body)
   if payload.get('error'):raise ValueError(payload)
   path.write_bytes(body)
   request_path.write_text(json.dumps({'url':url,'params':params,'fetched_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(body).hexdigest(),'source':'Open-Meteo Flood API / GloFAS v4 consolidated model; not gauge observations'},ensure_ascii=False,indent=2))
  body=path.read_bytes();meta=json.loads(request_path.read_text());digest=hashlib.sha256(body).hexdigest()
  if digest!=meta['sha256']:raise ValueError('Hydrology SHA-256 mismatch: '+name)
  p=json.loads(body)
  if p.get('utc_offset_seconds')!=0:raise ValueError('Model day must use UTC')
  if p['daily_units'].get('river_discharge')!='m³/s':raise ValueError('Unexpected discharge unit')
  df=pd.DataFrame({'location':name,'date':pd.to_datetime(p['daily']['time']),'river_discharge_m3s':p['daily']['river_discharge']})
  dates=pd.date_range(PARAMS['start_date'],PARAMS['end_date'])
  if not df.date.equals(pd.Series(dates)):raise ValueError('Missing/duplicate model date: '+name)
  df['river_discharge_m3s']=pd.to_numeric(df.river_discharge_m3s,errors='coerce')
  df['quality_flag']=np.where(df.river_discharge_m3s.isna(),'missing',np.where(df.river_discharge_m3s<0,'negative','valid'))
  df['grid_latitude']=p['latitude'];df['grid_longitude']=p['longitude'];df['source_model']='GloFAS_v4_consolidated';df['timezone']='UTC'
  valid=df.loc[df.quality_flag.eq('valid'),'river_discharge_m3s']
  frames.append(df)
  summary.append({'location':name,'n_total':len(df),'n_valid':len(valid),'n_missing':int(df.quality_flag.eq('missing').sum()),'n_negative':int(df.quality_flag.eq('negative').sum()),'grid_latitude':p['latitude'],'grid_longitude':p['longitude'],'mean_m3s':float(valid.mean()),'median_m3s':float(valid.median()),'p95_m3s':float(valid.quantile(.95)),'max_m3s':float(valid.max())})
  provenance.append({**meta,'file':str(path.relative_to(ROOT)),'grid_latitude':p['latitude'],'grid_longitude':p['longitude'],'rows':len(df)})
 result=pd.concat(frames,ignore_index=True)
 result.to_csv(OUT/'daily.csv',index=False)
 pd.DataFrame(summary).to_csv(OUT/'summary.csv',index=False)
 (OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
 monthly=result[result.quality_flag.eq('valid')].assign(month=lambda d:d.date.dt.month).groupby(['location','month']).river_discharge_m3s.median().reset_index()
 monthly.to_csv(OUT/'monthly.csv',index=False)
 fig,axs=plt.subplots(3,1,figsize=(9,6.5),sharex=True,layout='constrained')
 for ax,(name,g) in zip(axs,monthly.groupby('location')):
  ax.plot(g.month,g.river_discharge_m3s,marker='o');ax.set_title(name+' · GloFAS v4 consolidated · UTC · 2017–2021',fontsize=10);ax.set_ylabel('m³/s');ax.grid(alpha=.3)
 axs[-1].set_xlabel('Tháng');axs[-1].set_xticks(range(1,13))
 fig.savefig(OUT/'monthly.png',dpi=160);plt.close(fig)
 print('Hydrology replay:',result.shape,'rows/columns;',summary)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--refresh',action='store_true');run(p.parse_args().refresh)
