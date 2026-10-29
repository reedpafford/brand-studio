"""Reading a brand's website (flows BR2): the safe fetcher, with the network mocked."""

import socket

import httpx2 as httpx
import pytest

from app import site_fetch
from app.site_fetch import Refused, check_address, fetch, read_page


def _dns(table: dict[str, str]):
    def resolve(host, port, proto=0):
        if host not in table:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET, socket.SOCK_STREAM, proto, "", (table[host], port))]

    return resolve


PUBLIC = _dns({"shop.example": "93.184.216.34", "cdn.example": "93.184.216.35",
               "inside.example": "10.0.0.5", "home.example": "127.0.0.1",
               "meta.example": "169.254.169.254", "v6.example": "::1"})  # fmt: skip


@pytest.mark.parametrize("url", ["ftp://shop.example/", "file:///etc/passwd", "javascript:x",
                                 "shop.example", "https://"])  # fmt: skip
def test_only_web_addresses(url):
    with pytest.raises(Refused, match="Only web addresses"):
        check_address(url, PUBLIC)


@pytest.mark.parametrize("host", ["inside", "home", "meta", "v6"])
def test_private_loopback_and_link_local_addresses_are_refused(host):
    with pytest.raises(Refused, match="isn't a public website"):
        check_address(f"https://{host}.example/", PUBLIC)
    with pytest.raises(Refused, match="Couldn't find"):
        check_address("https://nowhere.example/", PUBLIC)
    assert check_address("https://shop.example/a", PUBLIC) == "93.184.216.34"  # the one to use


def _client(routes: dict[str, httpx.Response], seen: list | None = None) -> httpx.Client:
    """Answers by the name asked for (the Host header): the URL itself holds the address."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        asked = f"{request.url.scheme}://{request.headers['host']}{request.url.raw_path.decode()}"
        return routes[asked]

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_each_redirect_is_checked_again_and_there_are_few_of_them():
    to_inside = _client({"https://shop.example/": httpx.Response(
        302, headers={"location": "http://inside.example/admin"})})  # fmt: skip
    with pytest.raises(Refused, match="isn't a public website"):
        fetch("https://shop.example/", client=to_inside, resolve=PUBLIC)
    loop = _client({"https://shop.example/": httpx.Response(302, headers={"location": "/"})})
    with pytest.raises(Refused, match="too many times"):
        fetch("https://shop.example/", client=loop, resolve=PUBLIC)
    hop = _client({
        "https://shop.example/": httpx.Response(301, headers={"location": "https://cdn.example/x"}),
        "https://cdn.example/x": httpx.Response(200, text="<p>hi</p>",
                                                headers={"content-type": "text/html"}),
    })  # fmt: skip
    body, kind, url = fetch("https://shop.example/", client=hop, resolve=PUBLIC)
    assert (body, kind, url) == (b"<p>hi</p>", "text/html", "https://cdn.example/x")


def test_a_page_past_the_cap_or_an_error_is_refused():
    big = _client({"https://shop.example/": httpx.Response(200, content=b"x" * 50)})
    with pytest.raises(Refused, match="too big"):
        fetch("https://shop.example/", cap=10, client=big, resolve=PUBLIC)
    gone = _client({"https://shop.example/": httpx.Response(404)})
    with pytest.raises(Refused, match="404"):
        fetch("https://shop.example/", client=gone, resolve=PUBLIC)

    def down(request):
        raise httpx.ConnectTimeout("slow")

    slow = httpx.Client(transport=httpx.MockTransport(down))
    with pytest.raises(Refused, match="Couldn't reach"):
        fetch("https://shop.example/", client=slow, resolve=PUBLIC)
    assert site_fetch.TIMEOUT.read <= 10  # a short timeout


def test_a_page_gives_its_words_colours_and_logo():
    html = """<html><head><meta name="theme-color" content="#E4572E">
    <meta name="description" content="Treats dogs love.">
    <meta property="og:image" content="/img/logo.png"><style>.a{color:#fff;background:#29C}</style>
    <script>var x = "#123456";</script></head>
    <body><h1>Iron  Paws</h1><p>Chicken bites</p></body></html>"""
    page = read_page(html, "https://shop.example/home")
    assert page["text"] == "Iron Paws Chicken bites"
    assert page["description"] == "Treats dogs love."
    assert page["colours"] == ["#e4572e", "#2299cc"]  # white dropped, script ignored
    assert page["logo_url"] == "https://shop.example/img/logo.png"


TEREDO = "2001:0:4136:e378:8000:63bf:f5ff:fffe"  # its client address is 10.0.0.1


@pytest.mark.parametrize("ip", ["64:ff9b::7f00:1", "64:ff9b::a00:1", "::ffff:10.0.0.1",
                                "2002:7f00:1::", TEREDO,
                                "::127.0.0.1", "::10.0.0.1", "::93.184.216.34"])  # fmt: skip
def test_a_private_ipv4_inside_an_ipv6_address_is_refused(ip):
    with pytest.raises(Refused, match="isn't a public website"):
        check_address("https://x.example/", _dns({"x.example": ip}))
    assert check_address("https://x.example/", _dns({"x.example": "64:ff9b::5db8:d822"}))


def test_the_connection_goes_to_the_address_that_was_checked():
    seen = []
    page = _client({"https://shop.example/a": httpx.Response(200, text="ok")}, seen)
    fetch("https://shop.example/a", client=page, resolve=PUBLIC)
    asked = seen[0]
    assert asked.url.host == "93.184.216.34"  # not looked up again: DNS can't swap it
    assert asked.headers["host"] == "shop.example"
    assert asked.extensions["sni_hostname"] == "shop.example"  # TLS checks the real name


def test_a_slow_trickle_is_cut_off_at_the_deadline(monkeypatch):
    clock = iter(range(0, 100, 7))  # each read 7 s on: under 10 s each, past 20 s in all
    monkeypatch.setattr(site_fetch.time, "monotonic", lambda: next(clock))
    slow = _client({"https://shop.example/": httpx.Response(200, content=iter([b"a"] * 10))})
    with pytest.raises(Refused, match="too long"):
        fetch("https://shop.example/", client=slow, resolve=PUBLIC)


def test_no_proxy_from_the_environment():
    assert site_fetch.new_client().trust_env is False
