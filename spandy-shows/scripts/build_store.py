"""Pack a staged Windows desktop release using the identity reserved in Partner Center."""
import argparse
import json
import re
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("bundle", "makeappx", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    for key in ("name", "publisher", "publisher-display-name", "version"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}',args.name):
        parser.error('Use the exact Package/Identity/Name from Partner Center.')
    if not args.publisher.startswith('CN='):
        parser.error('Use the exact Package/Identity/Publisher from Partner Center, beginning CN=.')
    if not re.fullmatch(r'\d+\.\d+\.\d+\.0',args.version) or any(int(n)>65535 for n in args.version.split('.')):
        parser.error('Use a four-part Store version with final component 0 and components up to 65535.')
    bundle = args.bundle.resolve(strict=True)
    tool = args.makeappx.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(bundle) or output.exists() or output.suffix.lower() != ".msix":
        parser.error("Choose a new .msix file outside the staged app folder.")
    launcher = "Spandy Shows.exe"
    required = [launcher, "resources/app/main.cjs", "runtime/python/python.exe",
                "runtime/java/bin/javac.exe", "runtime/c/bin/gcc.exe", "runtime/c/bin/gdb.exe"]
    if any(not (bundle / item).is_file() for item in required):
        parser.error("The staged desktop release is incomplete.")
    assets = Path(__file__).resolve().parents[1] / "desktop" / "store"
    manifest = ET.parse(assets / "AppxManifest.xml")
    ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = manifest.find("m:Identity", ns)
    identity.attrib.update(Name=args.name, Publisher=args.publisher, Version=args.version)
    manifest.find("m:Properties/m:PublisherDisplayName", ns).text = args.publisher_display_name
    # Keep the namespace prefixes referenced in IgnorableNamespaces.
    for _, (prefix, uri) in ET.iterparse(assets / "AppxManifest.xml", events=["start-ns"]):
        ET.register_namespace(prefix, uri)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        temp = Path(temporary)
        manifest_file = temp / "AppxManifest.xml"
        manifest.write(manifest_file, encoding="utf-8", xml_declaration=True)
        marker = temp / 'store.json'
        marker.write_text(json.dumps({'distribution':'microsoft-store'}),encoding='utf-8')
        mapping = temp / "mapping.txt"
        with mapping.open("w", encoding="utf-8-sig") as stream:
            print("[Files]", file=stream)
            for path in sorted(bundle.rglob("*")):
                if path.is_file() and path.name not in ('Uninstall Spandy Shows.exe','spandy-install.ini','PACKAGE-MANIFEST.json') and '__pycache__' not in path.parts and path.suffix!='.pyc':
                    print(f'"{path}" "{path.relative_to(bundle)}"', file=stream)
            print(f'"{marker}" "resources\\app\\store.json"',file=stream)
            print(f'"{manifest_file}" "AppxManifest.xml"', file=stream)
            for logo in ("StoreLogo.png", "Square44.png", "Square150.png"):
                print(f'"{assets / logo}" "Assets\\{logo}"', file=stream)
        # Let the SDK validate and finalize the output in place. Windows can
        # retain a handle to a completed package during its security scan.
        subprocess.run([tool, "pack", "/no", "/f", mapping, "/p", output], check=True)
    print(output)


if __name__ == "__main__":
    main()
