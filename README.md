## Google Scholar Citation Crawler

### How-to

1. Install [scholarly](https://scholarly.readthedocs.io/en/stable/index.html)

```bash
pip install scholarly
```

2. Get a [ScraperAPI](https://www.scraperapi.com/pricing)

3. Run crawler

```bash
export SCRAPER_API_KEY=<your-api-key>
export AUTHOR_ID=<google-scholar-id>
python main.py
```

### JSON Format

```python
import json

with open('author_id.json', 'r') as f:
    author = json.load(f)
```

1. author keys: `pprint(author, depth=1)`

```yaml
{
  "affiliation": "University of Electronic Science and Technology of China",
  "citedby": 51,
  "citedby5y": 51,
  "cites_per_year": { ... },
  "coauthors": [...],
  "container_type": "Author",
  "email_domain": "@std.uestc.edu.cn",
  "filled": [...],
  "hindex": 2,
  "hindex5y": 2,
  "i10index": 2,
  "i10index5y": 2,
  "interests": [...],
  "name": "Zhi Lu",
  "organization": 9610860646987207346,
  "public_access": { ... },
  "publications": [...],
  "scholar_id": "WvoIsHkAAAAJ",
  "source": "AUTHOR_PROFILE_PAGE",
  "url_picture": "...",
}
```

2. author's publication: `pprint(author["publications"][0], depth=1)`

```yaml
{
  "author_pub_id": "WvoIsHkAAAAJ:4DMP91E08xMC",
  "bib": { ... },
  "citedby_publications": [...],
  "citedby_url": "...",
  "cites_id": [...],
  "cites_per_year": { ... },
  "container_type": "Publication",
  "filled": True,
  "mandates": [...],
  "num_citations": 36,
  "pub_url": "...",
  "public_access": True,
  "source": "AUTHOR_PUBLICATION_ENTRY",
  "url_related_articles": "...",
}
```

3 publication's citation: `pprint(author["publications"][0]["citedby_publications"][0], depth=1)`

```yaml
{
  "author_id": [...],
  "bib": { ... },
  "citedby_url": "...",
  "container_type": "Publication",
  "eprint_url": "...",
  "filled": False,
  "gsrank": 1,
  "num_citations": 49,
  "pub_url": "...",
  "source": "PUBLICATION_SEARCH_SNIPPET",
  "url_add_sclib": "...",
  "url_related_articles": "...",
  "url_scholarbib": "...",
}
```

### To-dos

- [ ] Updating citations incrementally
- [ ] Filling each citation
