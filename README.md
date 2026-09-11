# magnusmh.is

Personal homepage, served by GitHub Pages from this repository.

The repository name matters: a repo called `<username>.github.io` is a *user
site* and serves at the root. Any other name serves under `/reponame`.

## Files

| | |
|---|---|
| `index.html` | the homepage |
| `publications.html` | generated — do not hand-edit |
| `legacy.html` | the old RU page, converted to UTF-8, kept so nothing is lost |
| `CNAME` | the custom domain. **Do not delete** — removing it drops the domain on the next build |
| `scripts/dblp2html.py` | DBLP → `publications.html` |

## Publications

```sh
python3 scripts/dblp2html.py
```

Pulls your record straight from [DBLP](https://dblp.org/pid/h/MMHalldorsson.html) —
no local `.bib` files to keep in sync, and DBLP's own accented, disambiguated
names avoid the matching headaches a personal `.bib` corpus has. Groups by
year, bolds your name, and attaches an arXiv link to any entry that also has
a matching CoRR preprint (matched by title). A preprint with no published
version yet is listed on its own, linked straight to arXiv. Standard library
only.

Re-run it instead of editing HTML. Hand-maintenance is how the old page ended
up three years out of date.

## Setup, in order

Domain first — if DNS resolves before the custom domain is attached, GitHub
issues the certificate on the first attempt.

**1.** Register `magnusmh.is` at [ISNIC](https://www.isnic.is). DNS itself ended
up delegated to Cloudflare (nameservers `*.ns.cloudflare.com`) rather than
ISNIC's own — records below are managed there.

**2.** DNS records. The apex cannot be a CNAME, so it needs address records —
all four of each, they are one load-balanced set:

```
magnusmh.is.        A      185.199.108.153
magnusmh.is.        A      185.199.109.153
magnusmh.is.        A      185.199.110.153
magnusmh.is.        A      185.199.111.153
magnusmh.is.        AAAA   2606:50c0:8000::153
magnusmh.is.        AAAA   2606:50c0:8001::153
magnusmh.is.        AAAA   2606:50c0:8002::153
magnusmh.is.        AAAA   2606:50c0:8003::153
www.magnusmh.is.    CNAME  magnusmhalldorsson.github.io.
```

**3.** Create the GitHub repo `magnusmhalldorsson.github.io` and push.

**4.** Settings → Pages → Custom domain → `magnusmh.is`.

**5.** Wait for the certificate, then tick **Enforce HTTPS**. Usually minutes,
occasionally a day. The checkbox stays grayed out until it lands.

**6.** Settings → Pages → Verified domains, add the TXT record it gives you.
Stops anyone else attaching the domain to their Pages site if it ever lapses.

Check:

```sh
dig +short magnusmh.is
curl -sSI https://magnusmh.is | head -3
```

## Ask RU for a redirect

From `staff.ru.is/mmh/` to `magnusmh.is`. Push for **path-preserving** —
`staff.ru.is/mmh/papers/x.pdf` → `magnusmh.is/papers/x.pdf` — because the old
page has 119 links and papers cited from elsewhere are what break otherwise.
If they will only redirect the root, mirror the old paths here instead.

## Note on the old page

It was authored in ISO-8859-1 and the server migration to IIS dropped the
charset header, so browsers defaulting to UTF-8 mangled every Icelandic
character — including your own name. `legacy.html` is the same content
converted to UTF-8 with the charset declared. On your own host, nobody else's
migration can undo that.
