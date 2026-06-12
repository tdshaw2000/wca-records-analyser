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
const SECONDS_PAD = 2;
const RESULT_AXIS_PADDING_FRACTION = 0.05;
const FADED_LEGEND_COLOUR = "rgba(31, 41, 51, 0.35)";
const MOVES_UNIT = "moves";

function readSeries(elementId) {
    return JSON.parse(document.getElementById(elementId).textContent);
}

function resultBounds(points) {
    const values = points.map((point) => point.y);
    const lowest = Math.min(...values);
    const highest = Math.max(...values);
    const range = highest - lowest;
    const padding = (range || highest) * RESULT_AXIS_PADDING_FRACTION;
    return { min: Math.max(0, lowest - padding), max: highest + padding };
}

function dateBounds(points) {
    const dates = points.map((point) => point.x).sort();
    return { min: dates[0], max: dates[dates.length - 1] };
}

function fadeHiddenLegendLabels(chart) {
    const labels = Chart.defaults.plugins.legend.labels.generateLabels(chart);
    for (const label of labels) {
        if (!chart.isDatasetVisible(label.datasetIndex)) {
            label.hidden = false;
            label.fontColor = FADED_LEGEND_COLOUR;
            label.fillStyle = FADED_LEGEND_COLOUR;
            label.strokeStyle = FADED_LEGEND_COLOUR;
        }
    }
    return labels;
}

function formatAxisTick(value) {
    if (resultUnit === MOVES_UNIT) {
        return String(Math.round(value));
    }
    const totalSeconds = Math.round(value / CENTISECONDS_PER_SECOND);
    const minutes = Math.floor(totalSeconds / SECONDS_PER_MINUTE);
    const seconds = totalSeconds % SECONDS_PER_MINUTE;
    if (minutes) {
        return `${minutes}:${String(seconds).padStart(SECONDS_PAD, "0")}`;
    }
    return String(seconds);
}

const canvas = document.getElementById(CANVAS_ELEMENT_ID);
const resultUnit = canvas.dataset.resultUnit;
const singleSeries = readSeries(SINGLE_CHART_DATA_ELEMENT_ID);
const averageSeries = readSeries(AVERAGE_CHART_DATA_ELEMENT_ID);
const allPoints = [...singleSeries, ...averageSeries];
const resultRange = resultBounds(allPoints);
const dateRange = dateBounds(allPoints);

new Chart(canvas, {
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
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                type: "time",
                min: dateRange.min,
                max: dateRange.max,
                title: { display: true, text: TIME_PROGRESSION_AXIS_LABEL },
                ticks: { display: false },
                grid: { display: false },
            },
            y: {
                min: resultRange.min,
                max: resultRange.max,
                title: { display: true, text: RESULT_AXIS_LABEL },
                ticks: { callback: (value) => formatAxisTick(value) },
            },
        },
        plugins: {
            legend: {
                labels: { generateLabels: fadeHiddenLegendLabels },
            },
            tooltip: {
                callbacks: {
                    title: (items) => items[0].raw.x,
                    label: (context) => context.raw.display,
                },
            },
        },
    },
});
