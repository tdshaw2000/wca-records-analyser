(function () {
const OVERVIEW_MAP_COLOUR = "#7c3aed";
const BASE_RADIUS = 6;
const RADIUS_PER_PR = 1;
const MAX_RADIUS = 20;
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function circleRadius(cityGroup) {
    return Math.min(BASE_RADIUS + (cityGroup.total - 1) * RADIUS_PER_PR, MAX_RADIUS);
}

function buildTooltip(cityGroup) {
    const rows = cityGroup.events
        .map(
            (e) =>
                `<tr><td>${e.name}</td><td>${e.singles}</td><td>${e.averages || "—"}</td></tr>`
        )
        .join("");
    return `<strong>${cityGroup.city}</strong><table><tr><th></th><th>Single</th><th>Average</th></tr>${rows}</table>`;
}

function initMap() {
    const container = document.getElementById("overview-map");
    if (!container) return;
    const url = container.dataset["map-url"] || container.getAttribute("data-map-url");

    fetch(url)
        .then((r) => r.json())
        .then((series) => {
            const defaultCenter = series.length
                ? [series[0].lat, series[0].lng]
                : [20, 0];
            const defaultZoom = series.length ? 6 : 2;

            const map = L.map("overview-map", { zoomControl: true }).setView(
                defaultCenter,
                defaultZoom
            );

            L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION }).addTo(map);

            const markers = series.map((cityGroup) =>
                L.circleMarker([cityGroup.lat, cityGroup.lng], {
                    radius: circleRadius(cityGroup),
                    color: OVERVIEW_MAP_COLOUR,
                    fillColor: OVERVIEW_MAP_COLOUR,
                    fillOpacity: 0.7,
                    weight: 1.5,
                }).bindPopup(buildTooltip(cityGroup), { maxHeight: 300 })
            );
            L.layerGroup(markers).addTo(map);

            if (series.length > 1) {
                const bounds = L.latLngBounds(
                    series.map((g) => [g.lat, g.lng])
                );
                map.fitBounds(bounds, { padding: [40, 40] });
            }
        });
}

document.addEventListener("DOMContentLoaded", initMap);
}());
