from __future__ import annotations
from pathlib import Path
from datetime import date
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BASE="https://knowthegulf.com"
EXCLUDE={".git","node_modules"}

def lastmod(path: Path)->str:
    rel=path.relative_to(ROOT).as_posix()
    try:
        out=subprocess.check_output(["git","log","-1","--format=%cs","--",rel],cwd=ROOT,text=True).strip()
        if out: return out
    except Exception:
        pass
    return date.today().isoformat()

def route_for(path: Path)->str|None:
    rel=path.relative_to(ROOT)
    if any(part in EXCLUDE or part.startswith(".") for part in rel.parts): return None
    if rel.name!="index.html": return None
    parent=rel.parent.as_posix()
    return "/" if parent=="." else f"/{parent}/"

def main():
    routes=[]
    for p in ROOT.rglob("index.html"):
        route=route_for(p)
        if route: routes.append((route,lastmod(p)))
    routes.sort(key=lambda x:(x[0]!="/",x[0]))
    ns="http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("",ns)
    root=ET.Element(f"{{{ns}}}urlset")
    for route,modified in routes:
        u=ET.SubElement(root,f"{{{ns}}}url")
        ET.SubElement(u,f"{{{ns}}}loc").text=BASE+route
        ET.SubElement(u,f"{{{ns}}}lastmod").text=modified
    ET.indent(root,space="  ")
    ET.ElementTree(root).write(ROOT/"sitemap.xml",encoding="utf-8",xml_declaration=True)
    print(f"Generated sitemap with {len(routes)} routes")
if __name__=="__main__": main()
