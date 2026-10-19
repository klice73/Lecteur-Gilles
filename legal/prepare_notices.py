from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'legal/licenses'
for target in (ROOT/'app/src/main/assets/licenses',ROOT/'windows/licences'):
 target.mkdir(parents=True,exist_ok=True)
 for p in source.rglob('*'):
  if p.is_file():shutil.copy2(p,target/('__'.join(p.relative_to(source).parts)))
print('Notices installed')
