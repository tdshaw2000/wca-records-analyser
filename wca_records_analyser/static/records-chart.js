const SINGLE_CHART_DATA_ELEMENT_ID = "single-chart-data";
const AVERAGE_CHART_DATA_ELEMENT_ID = "average-chart-data";
const CANVAS_ELEMENT_ID = "record-progression";
const SINGLE_LABEL = "Personal record single";
const AVERAGE_LABEL = "Personal record average";
const SINGLE_COLOUR = "#2563eb";
const AVERAGE_COLOUR = "#15803d";
const DATE_AXIS_LABEL = "Date";
const TIME_AXIS_LABEL = "Time";

function readSeries(elementId) {
    return JSON.parse(document.getElementById(elementId).textContent);
}

new Chart(document.getElementById(CANVAS_ELEMENT_ID), {
    type: "line",
    data: {
        datasets: [
            {
                label: SINGLE_LABEL,
                data: readSeries(SINGLE_CHART_DATA_ELEMENT_ID),
                borderColor: SINGLE_COLOUR,
                backgroundColor: SINGLE_COLOUR,
            },
            {
                label: AVERAGE_LABEL,
                data: readSeries(AVERAGE_CHART_DATA_ELEMENT_ID),
                borderColor: AVERAGE_COLOUR,
                backgroundColor: AVERAGE_COLOUR,
            },
        ],
    },
    options: {
        scales: {
            x: {
                type: "time",
                title: { display: true, text: DATE_AXIS_LABEL },
            },
            y: {
                title: { display: true, text: TIME_AXIS_LABEL },
            },
        },
        plugins: {
            tooltip: {
                callbacks: {
                    label: (context) => context.raw.display,
                },
            },
        },
    },
});
