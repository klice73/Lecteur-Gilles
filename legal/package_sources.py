"""Prepare reviewed application sources and pinned upstream archives; see AUDIT.md."""
from pathlib import Path
import urllib.request,json,hashlib,subprocess,zipfile,os,concurrent.futures
ROOT=Path(__file__).resolve().parents[1]
DEST=Path(os.environ.get('GILLES_SOURCE_CACHE',str(ROOT/'.source-cache')))
DEST.mkdir(parents=True,exist_ok=True)
entries=json.loads((ROOT/'legal/source-manifest.json').read_text())
def fetch(e):
 p=DEST/e['file']
 if not p.exists():
  pending=p.with_suffix(p.suffix+'.part')
  request=urllib.request.Request(e['url'],headers={'User-Agent':'Lecteur-Gilles-source-preparation'})
  with urllib.request.urlopen(request,timeout=180) as source,pending.open('wb') as out:
   while block:=source.read(1024*1024):out.write(block)
  pending.replace(p)
 with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
 if actual!=e['sha256']:raise RuntimeError('Source hash mismatch: '+e['name'])
 return p
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:archives=list(pool.map(fetch,entries))
files=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'ls-files','-z'],cwd=ROOT).decode().split('\0')
output=ROOT/'Lecteur-Gilles-Sources-preparation.zip'
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
 for name in files:
  if not name:continue
  f=ROOT/name
  if not f.is_file():raise RuntimeError('Missing tracked source: '+name)
  if any(part.lower() in ('config','runtime','voix','.git') for part in Path(name).parts) or name.lower().endswith(('.jks','.keystore','.apk','.exe','.wav')):raise RuntimeError('Unexpected private/binary path: '+name)
  z.write(f,'application/'+name)
 for f in archives:z.write(f,'sources-tierces/'+f.name)
print(output.name,output.stat().st_size)
