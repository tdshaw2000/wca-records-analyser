const OVERVIEW_ROWS_ID = "overview-rows";
const ROWS_URL_ATTRIBUTE = "data-rows-url";

async function loadOverviewRows() {
    const body = document.getElementById(OVERVIEW_ROWS_ID);
    if (!body) {
        return;
    }
    const rowsUrl = body.getAttribute(ROWS_URL_ATTRIBUTE);
    if (!rowsUrl) {
        return;
    }
    const response = await fetch(rowsUrl);
    if (response.ok) {
        body.innerHTML = await response.text();
    }
}

document.addEventListener("DOMContentLoaded", loadOverviewRows);
