const CHART_DATA_ELEMENT_ID = "chart-data";
const CANVAS_ELEMENT_ID = "record-progression";
const SINGLE_LABEL = "Personal record single";
const DATE_AXIS_LABEL = "Date";
const SINGLE_AXIS_LABEL = "Single";

const series = JSON.parse(document.getElementById(CHART_DATA_ELEMENT_ID).textContent);

new Chart(document.getElementById(CANVAS_ELEMENT_ID), {
    type: "line",
    data: {
        datasets: [
            {
                label: SINGLE_LABEL,
                data: series,
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
                title: { display: true, text: SINGLE_AXIS_LABEL },
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
