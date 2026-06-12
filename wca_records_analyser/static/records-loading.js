const CHART_LOADING_ELEMENT_ID = "chart-loading";
const LOADING_CLASS = "is-loading";

function showChartLoading() {
    const overlay = document.getElementById(CHART_LOADING_ELEMENT_ID);
    if (overlay) {
        overlay.classList.add(LOADING_CLASS);
    }
}
