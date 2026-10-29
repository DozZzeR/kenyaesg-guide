"""Build the password-protected guide site into docs/.

Usage:
  SITE_USER=... SITE_PASSWORD=... python3 tools/build.py RU.md EN.md

The Markdown sources are NOT stored in this public repository. Only the
encrypted payloads (docs/*.enc.json) and the login shell (docs/index.html)
are published. Encryption: PBKDF2-HMAC-SHA256 -> AES-256-GCM, decrypted in
the browser with WebCrypto.
"""
import base64, json, os, re, secrets, sys
from pathlib import Path

import markdown
import markdown.extensions.toc
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
OUT = ROOT / "docs"
ITERATIONS = 600_000

HERO = {
    "ru": {
        "eyebrow": "KenyaESG · справочник для партнёров и клиентов · версия 2, 29.10.2026",
        "lede": "Что такое ESG и углеродный учёт, какие обязанности реально есть у кенийского завода, кто кого заставляет отчитываться, где теряются деньги и что может, а что не может сделать программа. Исходный текст проверен и исправлен; все исправления собраны в разделе 0.",
        "legend": ["проверено по первоисточнику", "вторичные источники", "не подтверждено, проверить перед публикацией"],
        "toc": "Содержание",
        "badges": ["проверено", "вторичный источник", "не подтверждено"],
    },
    "en": {
        "eyebrow": "KenyaESG · guide for partners and clients · version 2, 29 Oct 2026",
        "lede": "What ESG and carbon accounting are, which duties a Kenyan factory really has, who makes whom report, where money is lost, and what software can and cannot do. The original text was checked and corrected; all corrections are collected in section 0.",
        "legend": ["checked against the primary source", "secondary sources", "not confirmed, check before publishing"],
        "toc": "Contents",
        "badges": ["checked", "secondary source", "not confirmed"],
    },
}


PRESSURE = {
    "ru": (["Кто требует", "Через кого", "Что приходит на завод"], [
        ("NEMA / SWMA", "напрямую", "закон: EPR, лицензии, аудиты"),
        ("EPRA", "напрямую", "закон: энергоаудит, если больше 180 000 кВт·ч в год"),
        ("ЦБ Кении", "банк", "условия кредита, данные о выбросах"),
        ("ICPAK / NSE", "листинговый покупатель или материнская компания", "анкета поставщика"),
        ("Законы ЕС, цели SBTi", "европейский покупатель", "контракт, данные для CBAM"),
        ("Завод", "PRO, например KEPRO", "взносы и декларации (обратное направление)"),
    ]),
    "en": (["Who demands it", "Through whom", "What reaches the factory"], [
        ("NEMA / SWMA", "directly", "law: EPR, licences, audits"),
        ("EPRA", "directly", "law: energy audit above 180,000 kWh a year"),
        ("Central Bank of Kenya", "bank", "loan terms, emissions data"),
        ("ICPAK / NSE", "listed buyer or parent company", "supplier questionnaire"),
        ("EU law, SBTi targets", "European buyer", "contract, CBAM data"),
        ("Factory", "PRO, e.g. KEPRO", "fees and declarations (the other direction)"),
    ]),
}


def pressure_map(lang: str) -> str:
    head, rows = PRESSURE[lang]
    out = ['<div class="pmap" role="table">', '<div class="pm-row pm-head" role="row">']
    out += [f'<span role="columnheader">{h}</span>' for h in head] + ["</div>"]
    for a, b, c in rows:
        out.append(f'<div class="pm-row" role="row"><span role="cell" class="pm-src">{a}</span>'
                   f'<span role="cell" class="pm-via">{b}</span><span role="cell" class="pm-what">{c}</span></div>')
    return "\n".join(out + ["</div>"]) + "\n"


def render(md_path: Path, lang: str) -> dict:
    src = md_path.read_text(encoding="utf-8")
    lines = src.split("\n")
    title = lines[0].lstrip("# ").strip()
    body = "\n".join(lines[1:])
    body = re.sub(r"```mermaid\n.*?```", lambda m: pressure_map(lang), body, flags=re.S)
    cfg = {"toc": {"toc_depth": "2", "slugify": markdown.extensions.toc.slugify_unicode}}
    md = markdown.Markdown(extensions=["tables", "toc", "sane_lists"], extension_configs=cfg)
    html = md.convert(body)
    html = html[html.index("<h2"):]  # the intro paragraphs live in the hero
    html = re.sub(r"(<h2[^>]*>[^<]*</h2>\s*)(<ol>)", r'\1<div class="quick"></div>\2', html, count=1)
    h = HERO[lang]
    for mark, cls, tip in zip("✅🟡❓", ["ok", "mid", "q"], h["badges"]):
        html = html.replace(mark, f'<span class="b b-{cls}" title="{tip}">{mark}</span>')
    html = html.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    html = html.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')
    legend = "".join(
        f'<span><span class="b b-{c}">{m}</span> {t}</span>' for m, c, t in zip("✅🟡❓", ["ok", "mid", "q"], h["legend"])
    )
    page = (
        f'<header class="hero"><div class="eyebrow">{h["eyebrow"]}</div><h1>{title}</h1>'
        f'<p class="lede">{h["lede"]}</p><div class="legend">{legend}</div></header>'
        f'<div class="wrap"><nav class="toc" aria-label="{h["toc"]}"><span class="eyebrow">{h["toc"]}</span>{md.toc}</nav>'
        f"<main>{html}</main></div>"
    )
    return {"title": title, "html": page}


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    user = os.environ.get("SITE_USER", "").strip()
    password = os.environ.get("SITE_PASSWORD", "")
    if not user or len(password) < 10:
        sys.exit("Set SITE_USER and SITE_PASSWORD (at least 10 characters).")
    salt = secrets.token_bytes(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    key = kdf.derive(f"{user}\n{password}".encode())
    aes = AESGCM(key)
    OUT.mkdir(exist_ok=True)
    for lang, path in (("ru", sys.argv[1]), ("en", sys.argv[2])):
        doc = json.dumps(render(Path(path), lang), ensure_ascii=False).encode()
        iv = secrets.token_bytes(12)
        ct = aes.encrypt(iv, doc, None)
        (OUT / f"{lang}.enc.json").write_text(json.dumps({"iv": b64(iv), "ct": b64(ct)}))
    shell = (TOOLS / "shell.html").read_text(encoding="utf-8")
    shell = shell.replace("%%CSS%%", (TOOLS / "style.css").read_text(encoding="utf-8"))
    shell = shell.replace("%%SALT%%", b64(salt)).replace("%%ITER%%", str(ITERATIONS))
    (OUT / "index.html").write_text(shell, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print("Built docs/ (ru, en)")


if __name__ == "__main__":
    main()
