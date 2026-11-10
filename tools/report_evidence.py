"""Reproducible supplementary evidence from pinned inputs and held-out predictions.
No training or threshold selection is performed here. Test diagnostics are descriptive.
"""
from pathlib import Path
import json,hashlib,sqlite3,platform,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/report_evidence';CH=OUT/'charts'
LOC=['Ha_Noi','Da_Nang','TP_HCM']
LABEL={'Ha_Noi':'Hà Nội','Da_Nang':'Đà Nẵng','TP_HCM':'TP.HCM'}
def run():
 OUT.mkdir(exist_ok=True);CH.mkdir(exist_ok=True)
 d=pd.read_csv(ROOT/'outputs/real/clean.csv',parse_dates=['date'])
 p=pd.read_csv(ROOT/'outputs/real/predictions.csv',parse_dates=['target_date'])
 f=pd.read_csv(ROOT/'outputs/real/features.csv',parse_dates=['date','target_date'])
 h=pd.read_csv(ROOT/'outputs/hydrology/daily.csv',parse_dates=['date'])
 def save(name,rows):
  a=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows);a.to_csv(OUT/(name+'.csv'),index=False);return a
 def figsave(name,fig):
  fig.savefig(CH/(name+'.png'),dpi=180,bbox_inches='tight');plt.close(fig)
 rows=[]
 for folder in ['era5','hydrology']:
  for loc in LOC:
   path=ROOT/f'data/{folder}/{loc}.json';j=json.loads(path.read_text());rq=json.loads(path.with_name(loc+'_request.json').read_text())
   rows.append(dict(source=folder,location=loc,rows=len(j['daily']['time']),start=j['daily']['time'][0],end=j['daily']['time'][-1],latitude=j['latitude'],longitude=j['longitude'],timezone=j['timezone'],sha256=hashlib.sha256(path.read_bytes()).hexdigest(),url=rq['url'],retrieved=rq.get('fetched_at_utc',rq.get('retrieved_utc'))))
 save('source_inventory',rows)
 rows=[]
 for loc,g in d.groupby('location'):
  rows.append(dict(location=loc,n=len(g),missing=int(g.isna().sum().sum()),duplicate=int(g.duplicated('date').sum()),temp_mean=g.temp.mean(),temp_median=g.temp.median(),temp_min=g.temp.min(),temp_max=g.temp.max(),humidity_median=g.humidity.median(),rain_mean=g.rain.mean(),rain_max=g.rain.max(),wet_pct=100*g.rain.ge(1).mean(),zero_pct=100*g.rain.eq(0).mean()))
 save('location_profile',rows)
 rows=[]
 for loc,g in d.groupby('location'):
  sp=g[['temp','humidity','pressure','rain','wind','solar']].rank().corr()
  for a,b in [('humidity','rain'),('temp','humidity'),('temp','pressure'),('rain','solar')]:rows.append(dict(location=loc,pair=a+' / '+b,rho=sp.loc[a,b]))
 save('spearman_location',rows)
 monthly=save('monthly_weather',d.assign(month=d.date.dt.month,wet=d.rain.ge(1)).groupby(['location','month']).agg(n=('temp','size'),temp_median=('temp','median'),rain_mean=('rain','mean'),wet_pct=('wet',lambda s:100*s.mean())).reset_index())
 fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
 for loc in LOC:
  g=monthly[monthly.location.eq(loc)];ax[0].plot(g.month,g.rain_mean,marker='o',label=LABEL[loc]);ax[1].plot(g.month,g.wet_pct,marker='o',label=LABEL[loc])
 for a in ax:a.set_xlabel('Tháng');a.set_xticks(range(1,13));a.grid(alpha=.3)
 ax[0].set_ylabel('Lượng mưa trung bình (mm/ngày)');ax[1].set_ylabel('Ngày có lượng giáng thủy ≥1 mm (%)');ax[0].legend();figsave('monthly_rain',fig)
 fig,axs=plt.subplots(1,3,figsize=(10,3.6),layout='constrained')
 for ax,var,lab in zip(axs,['temp','humidity','rain'],['Nhiệt độ (°C)','Độ ẩm (%)','Giáng thủy (mm/ngày)']):
  ax.boxplot([d.loc[d.location.eq(l),var] for l in LOC],tick_labels=[LABEL[l] for l in LOC],showfliers=False);ax.set_ylabel(lab);ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.3)
 figsave('location_distributions',fig)
 split=save('split_inventory',f.assign(wet=f.target_rain.ge(1)).groupby('split').agg(n=('location','size'),date_min=('date','min'),date_max=('date','max'),target_min=('target_date','min'),target_max=('target_date','max'),wet_n=('wet','sum'),wet_pct=('wet',lambda x:100*x.mean())).reset_index())
 rows=[];cal=[]
 for loc,g in [('ALL',p),*list(p.groupby('location'))]:
  yt=g.target_rain.ge(1).to_numpy();yp=g.rain_prediction.to_numpy().astype(bool);q=g.rain_probability.to_numpy();tp=int((yt&yp).sum());fp=int((~yt&yp).sum());fn=int((yt&~yp).sum());tn=int((~yt&~yp).sum())
  rows.append(dict(location=loc,n=len(g),TP=tp,FP=fp,FN=fn,TN=tn,precision=tp/(tp+fp),recall=tp/(tp+fn),F1=2*tp/(2*tp+fp+fn),Brier=np.mean((q-yt)**2),wet_pct=yt.mean()*100))
 save('rain_confusion',rows)
 p['error']=p.R3-p.target_temp;p['abs_error']=p.error.abs();p['month']=p.target_date.dt.month
 monthlyerr=[]
 for (loc,m),g in p.groupby(['location','month']):monthlyerr.append(dict(location=loc,month=m,n=len(g),RMSE=np.sqrt(np.mean(g.error**2)),MAE=g.abs_error.mean(),bias=g.error.mean(),Persistence_RMSE=np.sqrt(np.mean((g.Persistence-g.target_temp)**2))))
 me=save('monthly_errors',monthlyerr)
 save('largest_errors',p.nlargest(6,'abs_error')[['location','target_date','target_temp','R3','Persistence','error','abs_error']])
 q=p.rain_probability.to_numpy();yt=p.target_rain.ge(1).to_numpy()
 for i in range(10):
  mask=(q>=i/10)&((q<(i+1)/10) if i<9 else (q<=1));n=int(mask.sum())
  if n:cal.append(dict(bin_left=i/10,bin_right=(i+1)/10,n=n,prob_mean=float(q[mask].mean()),observed_rate=float(yt[mask].mean())))
 ca=save('calibration',cal)
 fig,axs=plt.subplots(1,2,figsize=(10,3.8),layout='constrained');axs[0].plot([0,1],[0,1],'--',color='gray');axs[0].plot(ca.prob_mean,ca.observed_rate,'o-');axs[0].set(xlabel='Xác suất dự báo trung bình',ylabel='Tần suất ngày mưa',xlim=(0,1),ylim=(0,1));axs[1].bar(ca.prob_mean,ca.n,width=.065,color='#367b9b');axs[1].set(xlabel='Xác suất dự báo trung bình',ylabel='Số mẫu trong khoảng');figsave('rain_calibration',fig)
 fig,axs=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
 for loc in LOC:
  g=me[me.location.eq(loc)];axs[0].plot(g.month,g.RMSE,'o-',label=LABEL[loc]);axs[1].plot(g.month,g.bias,'o-',label=LABEL[loc])
 axs[0].set(ylabel='RMSE R3 (°C)',xlabel='Tháng Test 2025');axs[1].set(ylabel='Sai số có dấu R3 − ERA5 (°C)',xlabel='Tháng Test 2025');axs[1].axhline(0,color='gray',lw=.8);axs[0].legend()
 for ax in axs:ax.set_xticks(range(1,13));ax.grid(alpha=.3)
 figsave('monthly_errors',fig)
 fig,ax=plt.subplots(figsize=(7.8,3.7),layout='constrained')
 for loc in LOC:
  g=p[p.location.eq(loc)];a=np.sort(g.abs_error);ax.plot(a,np.arange(1,len(a)+1)/len(a),label=LABEL[loc])
 ax.set(xlabel='Sai số tuyệt đối R3 (°C)',ylabel='Tỷ lệ tích lũy');ax.legend();ax.grid(alpha=.3);figsave('error_ecdf',fig)
 yagi=save('event_window',d[d.location.eq('Ha_Noi')&d.date.between('2024-09-04','2024-09-12')][['date','temp','pressure','rain','wind']])
 fig,axs=plt.subplots(2,1,figsize=(9,4.5),sharex=True,layout='constrained');axs[0].bar(yagi.date,yagi.rain,color='#397b9b');axs[0].set_ylabel('Giáng thủy (mm/ngày)');axs[1].plot(yagi.date,yagi.pressure,'o-',color='#bd5a45');axs[1].set_ylabel('Áp suất mực biển (hPa)');axs[1].tick_params(axis='x',rotation=25);figsave('event_window',fig)
 hyd=[]
 for loc,g in h.groupby('location'):
  v=g.loc[g.quality_flag.eq('valid'),'river_discharge_m3s']
  hyd.append(dict(location=loc,n=len(v),zero_n=int(v.eq(0).sum()),min=float(v.min()),q1=float(v.quantile(.25)),median=float(v.median()),q3=float(v.quantile(.75)),p95=float(v.quantile(.95)),max=float(v.max())))
 save('hydrology_quantiles',hyd)
 fig,axs=plt.subplots(1,3,figsize=(10,3.8),layout='constrained')
 for ax,loc in zip(axs,LOC):
  v=np.sort(h.loc[h.location.eq(loc),'river_discharge_m3s'])[::-1];ax.plot(np.arange(1,len(v)+1)/(len(v)+1)*100,v);ax.set(title=LABEL[loc],xlabel='Tỷ lệ vượt thực nghiệm (%)',ylabel='Lưu lượng mô hình (m³/s)');ax.grid(alpha=.3)
 figsave('flow_duration',fig)
 with sqlite3.connect(ROOT/'outputs/kttv_weather.sqlite') as conn:
  query="SELECT location, COUNT(*) AS n, ROUND(SUM(rain_mm),1) AS rain_sum_mm FROM era5_daily GROUP BY location ORDER BY location"
  save('sql_era5_totals',pd.read_sql_query(query,conn));(OUT/'sql_queries.sql').write_text(query+';\n')
 manifest={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(OUT.glob('*.csv'))}
 (OUT/'manifest.json').write_text(json.dumps({'purpose':'Recomputed descriptive diagnostics; no test-set tuning','python':platform.python_version(),'inputs':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [ROOT/'outputs/real/clean.csv',ROOT/'outputs/real/predictions.csv',ROOT/'outputs/hydrology/daily.csv']},'outputs':manifest},indent=2))
 print('Supplementary evidence:',len(manifest),'CSV tables,',len(list(CH.glob('*.png'))),'figures')
if __name__=='__main__':run()
