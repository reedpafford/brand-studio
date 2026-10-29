"""Reading a brand's website (flows BR2): the one place the app fetches an address someone
typed. Only http(s); the host is resolved and private, loopback, link-local and other
internal addresses are refused (also inside IPv6 forms such as NAT64), again on every
redirect (3 at most); the connection goes to the address that was checked, never through an
environment proxy; a short timeout per read, a deadline for the whole fetch and a size cap.
What it keeps of a page is plain: its words, its meta description, the colours it names
and its logo's address. Real fetching only behind BS_SITE_READ_REAL (off)."""

import ipaddress
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx2 as httpx

TIMEOUT = httpx.Timeout(10.0, connect=5.0)  # each read
DEADLINE = 20.0  # the whole fetch, redirects and all: a slow trickle is cut off
PAGE_BYTES, LOGO_BYTES = 2 * 1024 * 1024, 5 * 1024 * 1024
REDIRECTS = 3
WORDS = 6000  # of the page's text, for the read
COLOURS = 6


class Refused(Exception):
    """An address we won't fetch, or a page we couldn't get: the read fails, uncharged."""


NAT64 = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("64:ff9b:1::/48"))
COMPATIBLE = ipaddress.ip_network("::/96")  # deprecated "IPv4-compatible" (::127.0.0.1)


def _public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Global and not multicast, and so is any IPv4 address carried inside an IPv6 one
    (mapped, 6to4, Teredo, NAT64), which could otherwise reach a private one. The old
    IPv4-compatible form (::/96) is refused outright."""
    if not ip.is_global or ip.is_multicast:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip in COMPATIBLE:  # deprecated, never a real site's address: refused outright
            return False
        inner = [ip.ipv4_mapped, ip.sixtofour, *(ip.teredo or ())]
        if any(ip in net for net in NAT64):
            inner.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
        return all(_public(v4) for v4 in inner if v4 is not None)
    return True


def check_address(url: str, resolve=socket.getaddrinfo) -> str:
    """The address to connect to (the one checked) if the URL is http(s) to a public
    address, else Refused. Every address the name resolves to must be public."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Refused("Only web addresses (http or https) can be read.")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        found = resolve(parts.hostname, port, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError) as exc:
        raise Refused("Couldn't find that site.") from exc
    ips = [ipaddress.ip_address(sockaddr[0].split("%")[0]) for *_, sockaddr in found]
    if not ips or not all(_public(ip) for ip in ips):
        raise Refused("That address isn't a public website.")
    return str(ips[0])


def new_client() -> httpx.Client:
    """No redirects followed by itself, and no proxy from the environment: the connection
    goes where the check said."""
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=False)


def _pinned(url: str, ip: str) -> tuple[str, dict, dict]:
    """The URL with its host replaced by the checked address (so DNS can't swap it between
    the check and the connection), its Host header, and the TLS name to verify."""
    parts = urlsplit(url)
    host = f"[{ip}]" if ":" in ip else ip
    netloc = f"{host}:{parts.port}" if parts.port else host
    pinned = parts._replace(netloc=netloc).geturl()
    name = parts.hostname
    header = f"{name}:{parts.port}" if parts.port else name
    return pinned, {"Host": header}, {"sni_hostname": name}


def fetch(url: str, cap: int = PAGE_BYTES, client: httpx.Client | None = None,
          resolve=socket.getaddrinfo) -> tuple[bytes, str, str]:  # fmt: skip
    """(body, content type, final URL), each hop checked and connected to the address it
    checked; Refused past the size cap, the redirect limit or the deadline."""
    http = client or new_client()
    end = time.monotonic() + DEADLINE
    for _ in range(REDIRECTS + 1):
        if time.monotonic() > end:
            raise Refused("That site took too long to answer.")
        pinned, headers, extensions = _pinned(url, check_address(url, resolve))
        headers["User-Agent"] = "BrandStudio/1.0"
        try:
            with http.stream("GET", pinned, headers=headers, extensions=extensions) as r:
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
                    if time.monotonic() > end:
                        raise Refused("That site took too long to answer.")
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
