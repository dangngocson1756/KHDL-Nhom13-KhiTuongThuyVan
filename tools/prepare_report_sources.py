"""Refresh source text, diagrams and supporting docs after a data run; no Word/PDF conversion."""
from report_extended import write_source
if __name__=='__main__':
    write_source()
    print('ERA5-first report sources and supporting docs refreshed.')
