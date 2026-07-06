const SEARCH_INPUT_ID = "name";
const SUGGESTIONS_ID = "search-suggestions";
const SEARCH_ENDPOINT = "/api/search";
const OVERVIEW_PATH = "/overview";
const MINIMUM_SEARCH_LENGTH = 3;
const DEBOUNCE_MILLISECONDS = 250;

const input = document.getElementById(SEARCH_INPUT_ID);
const suggestions = document.getElementById(SUGGESTIONS_ID);

let debounceTimer = null;
let inFlightRequest = null;

function hideSuggestions() {
    suggestions.replaceChildren();
    suggestions.hidden = true;
}

function showSuggestions(competitors) {
    suggestions.replaceChildren();
    if (competitors.length === 0) {
        suggestions.hidden = true;
        return;
    }
    for (const competitor of competitors) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = `${OVERVIEW_PATH}?wca_id=${encodeURIComponent(competitor.wca_id)}`;
        link.textContent = competitor.name;
        item.appendChild(link);
        suggestions.appendChild(item);
    }
    suggestions.hidden = false;
}

async function fetchSuggestions(query) {
    // Abort a still-pending request so its late response can't overwrite a newer one.
    if (inFlightRequest) {
        inFlightRequest.abort();
    }
    inFlightRequest = new AbortController();
    try {
        const url = `${SEARCH_ENDPOINT}?q=${encodeURIComponent(query)}`;
        const response = await fetch(url, { signal: inFlightRequest.signal });
        if (response.ok) {
            showSuggestions(await response.json());
        }
    } catch (error) {
        if (error.name !== "AbortError") {
            hideSuggestions();
        }
    }
}

function onInput() {
    const query = input.value.trim();
    window.clearTimeout(debounceTimer);
    if (query.length < MINIMUM_SEARCH_LENGTH) {
        if (inFlightRequest) {
            inFlightRequest.abort();
        }
        hideSuggestions();
        return;
    }
    debounceTimer = window.setTimeout(() => fetchSuggestions(query), DEBOUNCE_MILLISECONDS);
}

if (input && suggestions) {
    input.addEventListener("input", onInput);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            hideSuggestions();
        }
    });
    document.addEventListener("click", (event) => {
        if (!suggestions.contains(event.target) && event.target !== input) {
            hideSuggestions();
        }
    });
}
