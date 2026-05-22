from sources import (
    USER_AGENTS,
    SourceConfig,
    clear_unhealthy_sources,
    fetch_source_results,
    get_enabled_sources,
    get_last_search_status,
    get_search_results,
    get_source_count,
    get_tor_session,
    load_source_configs,
    parse_search_html,
    search_sources,
    set_unhealthy_sources,
)


def _search_engines():
    return [{"name": source.name, "url": source.url_template} for source in load_source_configs()]


SEARCH_ENGINES = _search_engines()
DEFAULT_SEARCH_ENGINES = [engine["url"] for engine in SEARCH_ENGINES]


def fetch_search_results(endpoint, query):
    source = endpoint
    if isinstance(endpoint, str):
        source = SourceConfig(name=endpoint, url_template=endpoint)
    return fetch_source_results(source, query).get("results", [])
