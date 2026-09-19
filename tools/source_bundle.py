"""Create an allowlisted source delivery ZIP excluding private runtime paths.

Excludes runtime stores, git history, local environments and publication helpers.
The token-pattern check is an additional guard, not an exhaustive secret audit.
"""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES=('README.md','AUTHORS.md','workflow.txt','requirements.txt',
            'requirements-hosted.txt','requirements-video.txt','Dockerfile',
            '.dockerignore','.gitignore','.gitlab-ci.yml')
TREES=('ps1','web','tests','tools','data','specs','docs',
       'outputs/readme-update-966c976',*(f'outputs/step{i}' for i in range(1,9)),
       'outputs/step10/final-release','outputs/step10/video-frames')
STEP10_FILES=('README.md','acceptance.md','delivery-status.json','verification.json',
              'test-results.txt','reproduction-results.txt','upstream-check.json','video-manifest.json',
              'tracklight-walkthrough.srt')
TOKEN=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|glpat-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')


def main():
    files={ROOT/name for name in ROOT_FILES}
    for tree in TREES:
        files.update(p for p in (ROOT/tree).rglob('*') if p.is_file())
    files.update(ROOT/'outputs/step10'/name for name in STEP10_FILES)
    contents={}
    for path in sorted(files):
        relative=path.relative_to(ROOT)
        if '__pycache__' in relative.parts or path.suffix in ('.pyc','.pyo'):continue
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f'Unsafe source path: {relative}')
        data=path.read_bytes()
        if TOKEN.search(data):raise ValueError(f'Potential credential in {relative}; inspect locally')
        contents[relative.as_posix()]=data
    manifest={'files_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},
              'scope':'Allowlisted source, frozen inputs, reviewed specifications and delivery evidence; no git history or runtime/session data.',
              'token_pattern_check':'passed; limited known-token patterns, not an exhaustive secret audit'}
    target=ROOT/'outputs/step10/tracklight-source.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in contents.items():
            entry=zipfile.ZipInfo(name,date_time=(2026,9,19,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry,data)
        archive.writestr('SOURCE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'path':str(target),'files':len(contents),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
