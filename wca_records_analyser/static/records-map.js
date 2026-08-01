(function () {
const SINGLE_COLOUR = "#2563eb";
const AVERAGE_COLOUR = "#449964";
const HIDDEN_OPACITY = 0.15;
const BASE_RADIUS = 6;
const RADIUS_PER_PR = 3;
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function readJsonElement(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : [];
}

function circleRadius(cityGroup) {
    return BASE_RADIUS + (cityGroup.prs.length - 1) * RADIUS_PER_PR;
}

function buildTooltip(cityGroup) {
    const rows = cityGroup.prs
        .map((pr) => `<tr><td>${pr.date}</td><td>${pr.display}</td></tr>`)
        .join("");
    return `<strong>${cityGroup.city}</strong><table>${rows}</table>`;
}

function buildLayer(series, colour) {
    const markers = series.map((cityGroup) =>
        L.circleMarker([cityGroup.lat, cityGroup.lng], {
            radius: circleRadius(cityGroup),
            color: colour,
            fillColor: colour,
            fillOpacity: 0.7,
            weight: 1.5,
        }).bindTooltip(buildTooltip(cityGroup), { sticky: false })
    );
    return L.layerGroup(markers);
}

function buildLegend(map, layers) {
    const legend = L.control({ position: "bottomright" });
    legend.onAdd = function () {
        const div = L.DomUtil.create("div", "map-legend");
        layers.forEach(({ label, colour, layer }) => {
            const item = L.DomUtil.create("div", "legend-item", div);
            item.dataset.active = "true";

            const swatch = L.DomUtil.create("span", "legend-swatch", item);
            swatch.style.background = colour;

            const text = L.DomUtil.create("span", "legend-label", item);
            text.textContent = label;

            item.addEventListener("click", () => {
                const active = item.dataset.active === "true";
                if (active) {
                    map.removeLayer(layer);
                    item.dataset.active = "false";
                    item.style.opacity = HIDDEN_OPACITY;
                } else {
                    map.addLayer(layer);
                    item.dataset.active = "true";
                    item.style.opacity = "";
                }
            });
        });
        return div;
    };
    return legend;
}

function initMap() {
    const singleSeries = readJsonElement("single-map-data");
    const averageSeries = readJsonElement("average-map-data");

    const singleLayer = buildLayer(singleSeries, SINGLE_COLOUR);
    const averageLayer = buildLayer(averageSeries, AVERAGE_COLOUR);

    const allPoints = [...singleSeries, ...averageSeries];
    const defaultCenter = allPoints.length
        ? [allPoints[0].lat, allPoints[0].lng]
        : [20, 0];
    const defaultZoom = allPoints.length ? 6 : 2;

    const map = L.map("pr-map", { zoomControl: true }).setView(
        defaultCenter,
        defaultZoom
    );

    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION }).addTo(map);

    singleLayer.addTo(map);
    averageLayer.addTo(map);

    if (allPoints.length > 1) {
        const bounds = L.latLngBounds(
            allPoints.map((g) => [g.lat, g.lng])
        );
        map.fitBounds(bounds, { padding: [40, 40] });
    }

    const legend = buildLegend(map, [
        { label: "Single", colour: SINGLE_COLOUR, layer: singleLayer },
        { label: "Average", colour: AVERAGE_COLOUR, layer: averageLayer },
    ]);
    legend.addTo(map);
}

document.addEventListener("DOMContentLoaded", initMap);
}());
