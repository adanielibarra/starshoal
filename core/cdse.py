"""Copernicus Data Space Ecosystem (CDSE) client: token, OData search, download.

Pure Python (stdlib only), no QGIS imports, so it can be reused by other tools.
Endpoints documented at https://documentation.dataspace.copernicus.eu/APIs/OData.html
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

IDENTITY_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
                "protocol/openid-connect/token")
CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DOWNLOAD_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products({id})/$value"

PRODUCT_TYPES = {"L2A": "S2MSI2A", "L1C": "S2MSI1C"}


class CDSEError(Exception):
    pass


def _urlopen(req, timeout):
    """urlopen restricted to https (every URL here is a fixed CDSE endpoint)."""
    url = req.full_url if isinstance(req, urllib.request.Request) else req
    if not url.startswith("https://"):
        raise CDSEError(f"Refusing a non-https URL: {url[:60]}")
    return urllib.request.urlopen(req, timeout=timeout)  # nosec B310 - scheme checked above


def get_token(username, password, timeout=60):
    data = urllib.parse.urlencode({
        "client_id": "cdse-public",
        "grant_type": "password",
        "username": username,
        "password": password,
    }).encode()
    req = urllib.request.Request(
        IDENTITY_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with _urlopen(req, timeout) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        raise CDSEError(
            f"Could not get a CDSE token (HTTP {e.code}). "
            "Check username and password.") from e
    token = payload.get("access_token")
    if not token:
        raise CDSEError("CDSE answered without an access_token.")
    return token


def bbox_to_wkt(xmin, ymin, xmax, ymax):
    return (f"POLYGON(({xmin} {ymin},{xmax} {ymin},{xmax} {ymax},"
            f"{xmin} {ymax},{xmin} {ymin}))")


def build_filter(wkt_4326, start, end, product_type, max_cloud):
    parts = [
        "Collection/Name eq 'SENTINEL-2'",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt_4326}')",
        f"ContentDate/Start ge {start}T00:00:00.000Z",
        f"ContentDate/Start le {end}T23:59:59.999Z",
        ("Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
         f"and att/OData.CSC.StringAttribute/Value eq '{product_type}')"),
        ("Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
         f"and att/OData.CSC.DoubleAttribute/Value le {float(max_cloud):.2f})"),
    ]
    return " and ".join(parts)


_NAME_RE = re.compile(
    r"^(S2[ABC])_MSIL(1C|2A)_(\d{8}T\d{6})_N(\d{4})_R(\d{3})_T(\w{5})_")


def parse_name(name):
    """Split a Sentinel-2 product name into its parts (or None)."""
    m = _NAME_RE.match(name)
    if not m:
        return None
    sat, level, sensing, baseline, orbit, tile = m.groups()
    return {"sat": sat, "level": level, "sensing": sensing,
            "baseline": int(baseline), "orbit": orbit, "tile": tile}


def deduplicate(products):
    """Keep only the newest processing baseline for each tile + sensing time.

    CDSE can list the same acquisition twice (original + reprocessed).
    """
    best = {}
    for p in products:
        info = parse_name(p["name"])
        if info is None:
            best[p["id"]] = p
            continue
        key = (info["sensing"], info["tile"])
        if key not in best or info["baseline"] > parse_name(best[key]["name"])["baseline"]:
            best[key] = p
    return sorted(best.values(), key=lambda p: (p["date"] or "", p["name"]))


def search(wkt_4326, start, end, level="L2A", max_cloud=20, top=100, timeout=120):
    if level not in PRODUCT_TYPES:
        raise CDSEError(f"Unknown level {level}")
    params = {
        "$filter": build_filter(wkt_4326, start, end, PRODUCT_TYPES[level], max_cloud),
        "$orderby": "ContentDate/Start asc",
        "$top": str(int(top)),
        "$expand": "Attributes",
    }
    url = CATALOGUE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    try:
        with _urlopen(url, timeout) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise CDSEError(f"CDSE search failed (HTTP {e.code}): {body}") from e

    out = []
    for p in payload.get("value", []):
        attrs = {a.get("Name"): a.get("Value") for a in p.get("Attributes", [])}
        out.append({
            "id": p["Id"],
            "name": p["Name"],
            "date": (p.get("ContentDate") or {}).get("Start"),
            "cloud": attrs.get("cloudCover"),
            "size": p.get("ContentLength"),
            "online": p.get("Online", True),
        })
    return deduplicate(out)


def download(product, out_dir, token, progress=None, is_canceled=None,
             chunk=4 * 1024 * 1024, timeout=300):
    """Download one product zip. Returns the final path.

    progress(fraction) and is_canceled() are optional callbacks.
    Skips the download if a file with the expected size already exists.
    """
    os.makedirs(out_dir, exist_ok=True)
    name = product["name"]
    if name.endswith(".SAFE"):
        name = name[:-5]
    final = os.path.join(out_dir, name + ".zip")
    expected = product.get("size")
    if os.path.exists(final) and (not expected or os.path.getsize(final) == expected):
        return final

    url = DOWNLOAD_URL.format(id=product["id"])
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    part = final + ".part"
    try:
        with _urlopen(req, timeout) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or expected or 0)
            done = 0
            while True:
                if is_canceled and is_canceled():
                    raise CDSEError("Download canceled.")
                buf = r.read(chunk)
                if not buf:
                    break
                f.write(buf)
                done += len(buf)
                if progress and total:
                    progress(done / total)
    except urllib.error.HTTPError as e:
        if os.path.exists(part):
            os.remove(part)
        raise CDSEError(f"Download of {name} failed (HTTP {e.code}).") from e
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise

    if os.path.getsize(part) < 1024 * 1024:
        # CDSE sometimes answers with a tiny error file instead of an HTTP error
        with open(part, "rb") as f:
            head = f.read(300).decode(errors="replace")
        os.remove(part)
        raise CDSEError(f"Download of {name} returned a tiny file, probably an error: {head}")
    os.replace(part, final)
    return final
