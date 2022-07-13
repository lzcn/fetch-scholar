# %%
import json
import logging
import os

from scholarly import ProxyGenerator, scholarly

logging.basicConfig(level=logging.INFO)

# Set up a ProxyGenerator object to use free proxies
# This needs to be done only once per session
fill_article = os.environ.get("FILL_ARTICLE", False)
author_id = os.environ.get("AUTHOR_ID", None)
if author_id is None:
    logging.error("Author ID not set")
    exit(1)
filename = f"{author_id}.json"
# get author profile
author = scholarly.search_author_id(author_id)
# fill author information
author = scholarly.fill(author)
# fill author publications
# logging.info("Filling author publications")
# for publication in author["publications"]:
#     scholarly.fill(publication)


# %%
def save_data(finename, data):
    with open(finename, "w") as file:
        json.dump(data, file, indent=2)


def update_one_article(new_article, old_article):
    if new_article["num_citations"] > old_article["num_citations"]:
        logging.info(
            "New %d citations added for paper: %s",
            new_article["num_citations"] - old_article["num_citations"],
            new_article["bib"]["title"],
        )
    if not old_article["filled"] and fill_article:
        logging.info("Filling article: %s", new_article["bib"]["title"])
        new_article = scholarly.fill(new_article)
    for key, value in new_article.items():
        old_article[key] = value
    return old_article


def update_publications(new_publications, old_publications):
    if len(new_publications) > len(old_publications):
        logging.info("New %d publications to be added", len(new_publications) - len(old_publications))
    else:
        logging.info("No new publications added")
    publications = []
    for new_publication in new_publications:
        new_id = new_publication["author_pub_id"]
        found = False
        for old_publication in old_publications:
            if old_publication["author_pub_id"] == new_id:
                # found and update
                found = True
                publications.append(update_one_article(new_publication, old_publication))
                break
        if not found:
            logging.info("New publication: %s", new_publication["bib"]["title"])
            publications.append(new_publication)
    return publications


def update_author(new, old):
    if new["citedby"] > old["citedby"]:
        logging.info("New %d citations added", new["citedby"] - old["citedby"])
    else:
        logging.info("No new citations added")
    for key, value in new.items():
        if key == "publications":
            old["publications"] = update_publications(value, old["publications"])
        else:
            old[key] = value
    return old


if not os.path.exists(filename):
    save_data(filename, author)
else:
    with open(filename, "r") as file:
        file_data = json.load(file)
    author = update_author(author, file_data)
    save_data(filename, author)


# %%
# set proxy for updating citations
pg = ProxyGenerator()
proxy_api_key = os.environ.get("PROXY_API_KEY")
pg.ScraperAPI(proxy_api_key)
# pg.FreeProxies()
# pg.Tor_Internal(tor_cmd = "tor")
scholarly.use_proxy(pg)
num_publications = len(author["publications"])
for article_count, publication in enumerate(author["publications"]):
    if "citedby_publications" not in publication:
        publication["citedby_publications"] = []
    if len(publication["citedby_publications"]) == publication["num_citations"]:
        logging.info(
            "[%d]/[%d] No new citations for paper: %s", article_count + 1, num_publications, publication["bib"]["title"]
        )
        continue
    logging.info(
        "Adding %d new citations to paper %s",
        publication["num_citations"] - len(publication["citedby_publications"]),
        publication["bib"]["title"],
    )
    citedby_publications = []
    cite_count = 1
    num_new_citations = publication["num_citations"] - len(publication["citedby_publications"])
    for citation in scholarly.citedby(publication):
        # incrementally update citations
        # TODO: is this key unique?
        citekey = citation["bib"]["title"].lower() + citation["bib"]["year"]
        founded = False
        for publication in author["publications"]:
            if publication["bib"]["title"].lower() + publication["bib"]["year"] == citekey:
                founded = True
                break
        if not founded:
            citedby_publications.append(citation)
            logging.info(
                "Added citation for [%d]-th/[%d] article: [%d]/[%d] - %s",
                citation["bib"]["title"],
                article_count + 1,
                num_publications,
                cite_count,
                num_new_citations,
            )
            cite_count += 1
        if num_new_citations == len(citedby_publications):
            break
    publication["citedby_publications"] = citedby_publications + publication["citedby_publications"]
    save_data(filename, author)