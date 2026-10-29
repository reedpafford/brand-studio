"""Reading a brand's website (flows BR2): the one place the app fetches an address someone
typed. Only http(s); the host is resolved and private, loopback, link-local and other
internal addresses are refused, again on every redirect (3 at most); a short timeout and a
size cap. What it keeps of a page is plain: its words, its meta description, the colours it
names and its logo's address. Real fetching only behind BS_SITE_READ_REAL (off)."""

import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx2 as httpx

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
PAGE_BYTES, LOGO_BYTES = 2 * 1024 * 1024, 5 * 1024 * 1024
REDIRECTS = 3
WORDS = 6000  # of the page's text, for the read
COLOURS = 6


class Refused(Exception):
    """An address we won't fetch, or a page we couldn't get: the read fails, uncharged."""


def check_address(url: str, resolve=socket.getaddrinfo) -> str:
    """The URL if it's http(s) to a public address, else Refused."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Refused("Only web addresses (http or https) can be read.")
    try:
        found = resolve(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError) as exc:
        raise Refused("Couldn't find that site.") from exc
    for *_, sockaddr in found:
        ip = ipaddress.ip_address(sockaddr[0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise Refused("That address isn't a public website.")
    return url


def fetch(url: str, cap: int = PAGE_BYTES, client: httpx.Client | None = None,
          resolve=socket.getaddrinfo) -> tuple[bytes, str, str]:  # fmt: skip
    """(body, content type, final URL), each hop checked; Refused past the cap or limits."""
    client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
    for _ in range(REDIRECTS + 1):
        check_address(url, resolve)
        try:
            with client.stream("GET", url, headers={"User-Agent": "BrandStudio/1.0"}) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code >= 400:
                    raise Refused(f"The site answered {r.status_code}.")
                data = bytearray()
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > cap:
                        raise Refused("That page is too big to read.")
                kind = r.headers.get("content-type", "").split(";")[0].strip().lower()
                return bytes(data), kind, url
        except httpx.HTTPError as exc:
            raise Refused("Couldn't reach that site.") from exc
    raise Refused("That site redirects too many times.")


def read_site(url: str) -> dict:
    """A real read of one page (BS_SITE_READ_REAL): fetched safely, then read_page."""
    body, kind, final = fetch(url)
    if kind not in ("text/html", "application/xhtml+xml"):
        raise Refused("That address isn't a web page.")
    return read_page(body.decode("utf-8", errors="replace"), final)


def switched_off(url: str) -> dict:
    raise Refused("Reading websites is switched off.")


HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def _hex(value: str) -> str | None:
    m = HEX.search(value or "")
    if not m:
        return None
    h = m.group(0)[1:].lower()
    return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words: list[str] = []
        self.meta: dict[str, str] = {}
        self.icons: list[str] = []
        self.styles: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            self.meta.setdefault(key, a.get("content", ""))
        elif tag == "link" and "icon" in a.get("rel", "").lower() and a.get("href"):
            self.icons.append(a["href"])
        if a.get("style"):
            self.styles.append(a["style"])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self.lasttag == "style":
            self.styles.append(data)
        elif not self._skip and data.strip():
            self.words.append(" ".join(data.split()))


def read_page(html: str, url: str) -> dict:
    """What a read needs from a page: its words, description, colours and logo address."""
    page = _Page()
    page.feed(html)
    colours: list[str] = []
    for value in [page.meta.get("theme-color", ""), *page.styles]:
        for m in HEX.finditer(value):
            c = _hex(m.group(0))
            if c and c not in colours and c not in ("#ffffff", "#000000"):
                colours.append(c)
    logo = page.meta.get("og:image") or (page.icons[0] if page.icons else "")
    words = " ".join(page.words).split()
    return {
        "url": url,
        "title": page.meta.get("og:title", ""),
        "description": page.meta.get("description") or page.meta.get("og:description", ""),
        "text": " ".join(words[:WORDS]),
        "colours": colours[:COLOURS],
        "logo_url": urljoin(url, logo) if logo else "",
    }
