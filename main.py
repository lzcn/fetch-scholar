from scholarly import ProxyGenerator, scholarly

# Set up a ProxyGenerator object to use free proxies
# This needs to be done only once per session
pg = ProxyGenerator()
pg.FreeProxies()
scholarly.use_proxy(pg)

author = scholarly.search_author_id("MVOCn1AAAAAJ")
author = scholarly.fill(author)
scholarly.pprint(author)


# Take a closer look at the first publication
first_publication = author["publications"][0]
first_publication_filled = scholarly.fill(first_publication)
scholarly.pprint(first_publication_filled)

# Print the titles of the author's publications
publication_titles = [pub["bib"]["title"] for pub in author["publications"]]
print(publication_titles)

# Which papers cited that publication?
citations = [
    citation["bib"]["title"] for citation in scholarly.citedby(first_publication_filled)
]
print(citations)
