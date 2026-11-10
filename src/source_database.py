"""Load two real external sources in separate tables; never merge them into synthetic observations."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

def load_external_tables(conn, root: Path):
    conn.executescript((root/'sql/04_external_sources.sql').read_text())
    real=pd.read_csv(root/'outputs/real/clean.csv')
    grid={}
    for loc in real.location.unique():
        p=json.loads((root/f'data/era5/{loc}.json').read_text())
        grid[loc]=(p['latitude'],p['longitude'])
    rows=[]
    for x in real.itertuples():
        rows.append((x.location,x.date,x.temp,x.tmax,x.tmin,x.humidity,x.pressure,x.rain,x.wind,x.solar,*grid[x.location],'ECMWF_ERA5','UTC+07:00'))
    conn.executemany('INSERT INTO era5_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
    hydro=pd.read_csv(root/'outputs/hydrology/daily.csv').where(lambda d:pd.notnull(d),None)
    conn.executemany('INSERT INTO hydrology_daily VALUES (?,?,?,?,?,?,?,?)',hydro[['location','date','river_discharge_m3s','quality_flag','grid_latitude','grid_longitude','source_model','timezone']].itertuples(index=False,name=None))
