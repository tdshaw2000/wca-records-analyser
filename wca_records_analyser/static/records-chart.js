const SINGLE_CHART_DATA_ELEMENT_ID = "single-chart-data";
const AVERAGE_CHART_DATA_ELEMENT_ID = "average-chart-data";
const CANVAS_ELEMENT_ID = "record-progression";
const SINGLE_LABEL = "Personal record single";
const AVERAGE_LABEL = "Personal record average";
const SINGLE_COLOUR = "#2563eb";
const AVERAGE_COLOUR = "#15803d";
const TIME_PROGRESSION_AXIS_LABEL = "Time →";
const RESULT_AXIS_LABEL = "Result";
const CENTISECONDS_PER_SECOND = 100;
const SECONDS_PER_MINUTE = 60;
const CENTISECONDS_PER_MINUTE = CENTISECONDS_PER_SECOND * SECONDS_PER_MINUTE;
const HUNDREDTHS_PAD = 2;
const SECONDS_PAD = 2;

function readSeries(elementId) {
    return JSON.parse(document.getElementById(elementId).textContent);
}

function formatResult(centiseconds) {
    const total = Math.round(centiseconds);
    const minutes = Math.floor(total / CENTISECONDS_PER_MINUTE);
    const withinMinute = total % CENTISECONDS_PER_MINUTE;
    const seconds = Math.floor(withinMinute / CENTISECONDS_PER_SECOND);
    const hundredths = withinMinute % CENTISECONDS_PER_SECOND;
    const paddedHundredths = String(hundredths).padStart(HUNDREDTHS_PAD, "0");
    if (minutes) {
        const paddedSeconds = String(seconds).padStart(SECONDS_PAD, "0");
        return `${minutes}:${paddedSeconds}.${paddedHundredths}`;
    }
    return `${seconds}.${paddedHundredths}`;
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
                title: { display: true, text: TIME_PROGRESSION_AXIS_LABEL },
                ticks: { display: false },
                grid: { display: false },
            },
            y: {
                title: { display: true, text: RESULT_AXIS_LABEL },
                ticks: { callback: (value) => formatResult(value) },
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
