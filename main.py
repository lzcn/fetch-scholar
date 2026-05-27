import json
import logging
import sys
from pathlib import Path

from scholarly import ProxyGenerator, scholarly

LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"
LOGGER = logging.getLogger(__name__)
TRUTHY_VALUES = {"1", "true", "yes", "on"}
DEFAULT_CONFIG_PATH = Path("config.yaml")


def parse_config_value(value):
    value = value.strip()
    if value.lower() in TRUTHY_VALUES:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    return value


def load_config(path=DEFAULT_CONFIG_PATH):
    if not path.exists():
        return {}

    config = {}
    current_key = None
    with path.open("r") as file:
        for raw_line in file:
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("- ") and current_key:
                config.setdefault(current_key, []).append(parse_config_value(stripped[2:]))
                continue

            if ":" not in stripped:
                continue

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            config[key] = [] if not value else parse_config_value(value)

    return config


def config_value(config, *names):
    if not config:
        return None

    for name in names:
        value = config.get(name)
        if value:
            return value

    return None


def config_flag(config, name, default=False):
    value = config_value(config, name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY_VALUES


def read_author_id(config):
    author_id = config_value(config, "AUTHOR_ID")
    if author_id:
        return str(author_id)

    LOGGER.error("AUTHOR_ID is not set in config.yaml")
    sys.exit(1)


def read_scraper_api_key(config):
    config_key = config_value(config, "SCRAPER_API_KEY", "PROXY_API_KEY")
    if config_key:
        return str(config_key)

    proxy_api_keys = config.get("PROXY_API_KEYS")
    if proxy_api_keys:
        return str(proxy_api_keys[0])

    return None


def load_data(path):
    with path.open("r") as file:
        return json.load(file)


def save_data(path, data):
    with path.open("w") as file:
        json.dump(data, file, indent=2)


def fetch_author(author_id):
    author = scholarly.search_author_id(author_id)
    return scholarly.fill(author)


def update_one_article(new_article, old_article, fill_article=False):
    if new_article["num_citations"] > old_article["num_citations"]:
        LOGGER.info(
            "New %d citations added for paper: %s",
            new_article["num_citations"] - old_article["num_citations"],
            new_article["bib"]["title"],
        )

    if not old_article.get("filled") and fill_article:
        LOGGER.info("Filling article: %s", new_article["bib"]["title"])
        new_article = scholarly.fill(new_article)

    old_article.update(new_article)
    return old_article


def update_publications(new_publications, old_publications, fill_article=False):
    if len(new_publications) > len(old_publications):
        LOGGER.info("New %d publications to be added", len(new_publications) - len(old_publications))
    else:
        LOGGER.info("No new publications added")

    old_by_id = {publication["author_pub_id"]: publication for publication in old_publications}
    publications = []
    for new_publication in new_publications:
        new_id = new_publication["author_pub_id"]
        old_publication = old_by_id.get(new_id)
        if old_publication is None:
            LOGGER.info("New publication: %s", new_publication["bib"]["title"])
            publications.append(new_publication)
            continue

        publications.append(update_one_article(new_publication, old_publication, fill_article=fill_article))

    return publications


def normalize_text(value):
    if value is None:
        return ""
    return " ".join(str(value).casefold().split())


def sequence_identity(value):
    if not value:
        return None
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return str(value)


def citation_identity(citation):
    for field in ("pub_url", "url_scholarbib", "eprint_url"):
        value = citation.get(field)
        if value:
            return field, value

    cites_id = sequence_identity(citation.get("cites_id"))
    if cites_id:
        return "cites_id", cites_id

    bib = citation.get("bib", {})
    title = normalize_text(bib.get("title"))
    if not title:
        return None

    return (
        "bib",
        title,
        normalize_text(bib.get("author")),
        normalize_text(bib.get("pub_year")),
    )


def citation_title(citation):
    return citation.get("bib", {}).get("title", "<untitled>")


def maybe_fill_citation(citation, fill_citation=False):
    if not fill_citation or citation.get("filled"):
        return citation

    LOGGER.info("Filling citation: %s", citation_title(citation))
    filled_citation = scholarly.fill(citation)
    if filled_citation is not citation:
        citation.clear()
        citation.update(filled_citation)
    return citation


def merge_citation(new_citation, old_citation, fill_citation=False):
    was_filled = old_citation.get("filled")
    old_citation.update(new_citation)
    if was_filled and not new_citation.get("filled"):
        old_citation["filled"] = True
    return maybe_fill_citation(old_citation, fill_citation=fill_citation)


def citation_index(citations):
    index = {}
    for citation in citations:
        identity = citation_identity(citation)
        if identity is not None:
            index[identity] = citation
    return index


def save_progress(callback):
    if callback:
        callback()


def update_author(new_author, old_author, fill_article=False):
    if new_author["citedby"] > old_author["citedby"]:
        LOGGER.info("New %d citations added", new_author["citedby"] - old_author["citedby"])
    else:
        LOGGER.info("No new citations added")

    for key, value in new_author.items():
        if key == "publications":
            old_author["publications"] = update_publications(
                value,
                old_author["publications"],
                fill_article=fill_article,
            )
        else:
            old_author[key] = value

    return old_author


def load_or_update_author(path, fetched_author, fill_article=False):
    if not path.exists():
        save_data(path, fetched_author)
        return fetched_author

    saved_author = load_data(path)
    updated_author = update_author(fetched_author, saved_author, fill_article=fill_article)
    save_data(path, updated_author)
    return updated_author


def configure_proxy(scraper_api_key):
    if not scraper_api_key:
        LOGGER.warning("SCRAPER_API_KEY is not set; continuing without ScraperAPI proxy")
        return

    proxy_generator = ProxyGenerator()
    proxy_generator.ScraperAPI(scraper_api_key)
    scholarly.use_proxy(proxy_generator)


def fill_existing_citations(publication, fill_citation=False, on_update=None):
    if not fill_citation:
        return False

    updated = False
    citedby_publications = publication["citedby_publications"]
    for index, citation in enumerate(citedby_publications):
        if citation.get("filled"):
            continue
        citedby_publications[index] = maybe_fill_citation(citation, fill_citation=True)
        save_progress(on_update)
        updated = True
    return updated


def update_publication_citations(
    publication,
    article_count,
    num_publications,
    fill_citation=False,
    on_update=None,
):
    publication.setdefault("citedby_publications", [])

    existing_citations = publication["citedby_publications"]
    expected_new_count = max(0, publication["num_citations"] - len(existing_citations))
    filled_existing = fill_existing_citations(
        publication,
        fill_citation=fill_citation,
        on_update=on_update,
    )

    if expected_new_count == 0:
        LOGGER.info(
            "[%d]/[%d] No new citations for paper: %s",
            article_count,
            num_publications,
            publication["bib"]["title"],
        )
        return filled_existing, 0

    LOGGER.info(
        "Adding %d new citations to paper %s",
        expected_new_count,
        publication["bib"]["title"],
    )

    existing_by_identity = citation_index(existing_citations)
    new_count = 0
    updated = filled_existing

    for scanned_count, citation in enumerate(scholarly.citedby(publication), start=1):
        identity = citation_identity(citation)
        old_citation = existing_by_identity.get(identity)
        if identity is not None and old_citation is not None:
            merged_citation = merge_citation(citation, old_citation, fill_citation=fill_citation)
            existing_by_identity[identity] = merged_citation
            save_progress(on_update)
            updated = True
            continue

        citation = maybe_fill_citation(citation, fill_citation=fill_citation)
        existing_citations.append(citation)
        new_count += 1
        updated = True

        if identity is not None:
            existing_by_identity[identity] = citation

        save_progress(on_update)
        LOGGER.info(
            "Added new citation [%d]/[%d] after scanning [%d]: %s",
            new_count,
            expected_new_count,
            scanned_count,
            citation_title(citation),
        )

        if new_count >= expected_new_count:
            break

    return updated, new_count


def update_citation_publications(author, path, fill_citation=False):
    total_citations = author["citedby"]
    publications = author["publications"]
    num_publications = len(publications)
    added_citations = 0

    for article_count, publication in enumerate(publications, start=1):
        on_update = lambda: save_data(path, author)
        updated, new_count = update_publication_citations(
            publication,
            article_count,
            num_publications,
            fill_citation=fill_citation,
            on_update=on_update,
        )
        added_citations += new_count

        if updated and not new_count:
            save_data(path, author)

    LOGGER.info("Added %d new citations across %d total citations", added_citations, total_citations)


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    config = load_config()
    author_id = read_author_id(config)
    author_path = Path(f"{author_id}.json")
    fill_article = config_flag(config, "FILL_ARTICLE")
    fill_citation = config_flag(config, "FILL_CITATION") or config_flag(config, "FILL_CITATIONS")

    author = fetch_author(author_id)
    author = load_or_update_author(author_path, author, fill_article=fill_article)

    configure_proxy(read_scraper_api_key(config))
    update_citation_publications(author, author_path, fill_citation=fill_citation)


if __name__ == "__main__":
    main()
