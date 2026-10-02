import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/omnichar-char/src"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: A minimal manifest that passes the signature and version checks, so a crafted fixture proves the
#: one cap it targets rather than tripping an earlier guard.
MANIFEST = json.loads(
    '{"magic":"INLINECHAR","format_version":1,"char_id":"x","name":"Ada","created_at":0,'
    '"modified_at":0,"app":"inline-studio","app_version":"","refs":[],"derived":[],"text":{},'
    '"payloads":{},"scoring":{},"hints":[],"apply":{},"reserved":{}}'
)


def build(tmp_path, members, manifest=None, name="evil.char", attrs=None):
    """A .char with a valid manifest and whatever hostile members a test needs."""
    raw = json.dumps(manifest or MANIFEST, separators=(",", ":")).encode()
    target = tmp_path / name
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", raw, compress_type=zipfile.ZIP_DEFLATED)
        for member, data in members.items():
            info = zipfile.ZipInfo(member)
            if attrs and member in attrs:
                info.external_attr = attrs[member]
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    return target
