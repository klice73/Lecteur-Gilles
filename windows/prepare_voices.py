from pathlib import Path
import urllib.request,hashlib,json
ROOT=Path(__file__).resolve().parent
for item in json.loads((ROOT/'voices.sha256.json').read_text()):
 p=ROOT/'voix'/item['file'];p.parent.mkdir(exist_ok=True)
 if not p.exists():
  pending=p.with_suffix(p.suffix+'.part')
  with urllib.request.urlopen(item['url'],timeout=120) as source,pending.open('wb') as dest:
   while block:=source.read(1024*1024):dest.write(block)
  pending.replace(p)
 with p.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
 if actual!=item['sha256']:raise RuntimeError('Voice hash mismatch: '+item['file'])
print('Voices verified')
