const SINGLE_CHART_DATA_ELEMENT_ID = "single-chart-data";
const AVERAGE_CHART_DATA_ELEMENT_ID = "average-chart-data";
const CANVAS_ELEMENT_ID = "record-progression";
const SINGLE_LABEL = "Personal record single";
const AVERAGE_LABEL = "Personal record average";
const SINGLE_COLOUR = "#2563eb";
const AVERAGE_COLOUR = "#15803d";
const DATE_AXIS_LABEL = "Date";
const TIME_AXIS_LABEL = "Time";
const MULTI_YEAR_AXIS_UNIT = "year";
const SINGLE_YEAR_AXIS_UNIT = "month";

function readSeries(elementId) {
    return JSON.parse(document.getElementById(elementId).textContent);
}

function chooseDateAxisUnit(...serieses) {
    const years = new Set();
    for (const series of serieses) {
        for (const point of series) {
            years.add(new Date(point.x).getFullYear());
        }
    }
    return years.size > 1 ? MULTI_YEAR_AXIS_UNIT : SINGLE_YEAR_AXIS_UNIT;
}

const singleSeries = readSeries(SINGLE_CHART_DATA_ELEMENT_ID);
const averageSeries = readSeries(AVERAGE_CHART_DATA_ELEMENT_ID);

new Chart(document.getElementById(CANVAS_ELEMENT_ID), {
    type: "line",
    data: {
        datasets: [
            {
                label: SINGLE_LABEL,
                data: singleSeries,
                borderColor: SINGLE_COLOUR,
                backgroundColor: SINGLE_COLOUR,
            },
            {
                label: AVERAGE_LABEL,
                data: averageSeries,
                borderColor: AVERAGE_COLOUR,
                backgroundColor: AVERAGE_COLOUR,
            },
        ],
    },
    options: {
        scales: {
            x: {
                type: "time",
                time: { unit: chooseDateAxisUnit(singleSeries, averageSeries) },
                title: { display: true, text: DATE_AXIS_LABEL },
            },
            y: {
                title: { display: true, text: TIME_AXIS_LABEL },
            },
        },
        plugins: {
            tooltip: {
                callbacks: {
                    title: (items) => items[0].raw.x,
                    label: (context) => context.raw.display,
                },
            },
        },
    },
});
