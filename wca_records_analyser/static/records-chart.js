const SINGLE_CHART_DATA_ELEMENT_ID = "single-chart-data";
const AVERAGE_CHART_DATA_ELEMENT_ID = "average-chart-data";
const CANVAS_ELEMENT_ID = "record-progression";
const SINGLE_LABEL = "Single";
const AVERAGE_LABEL = "Average";
const SINGLE_COLOUR = "#2563eb";
const AVERAGE_COLOUR = "#449964";
const TIME_PROGRESSION_AXIS_LABEL = "Time →";
const RESULT_AXIS_LABEL = "Result";
const POINTS_AXIS_LABEL = "Points (solved − missed)";
const CENTISECONDS_PER_SECOND = 100;
const SECONDS_PER_MINUTE = 60;
const SECONDS_PAD = 2;
const RESULT_AXIS_PADDING_FRACTION = 0.05;
const FADED_LEGEND_COLOUR = "rgba(31, 41, 51, 0.35)";
const MOVES_UNIT = "moves";
const POINTS_UNIT = "points";

function readSeries(elementId) {
    const element = document.getElementById(elementId);
    return element ? JSON.parse(element.textContent) : [];
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
    if (resultUnit === MOVES_UNIT || resultUnit === POINTS_UNIT) {
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
const resultAxisLabel =
    resultUnit === POINTS_UNIT ? POINTS_AXIS_LABEL : RESULT_AXIS_LABEL;
const singleSeries = readSeries(SINGLE_CHART_DATA_ELEMENT_ID);
const averageSeries = readSeries(AVERAGE_CHART_DATA_ELEMENT_ID);
const allPoints = [...singleSeries, ...averageSeries];
const resultRange = resultBounds(allPoints);
const dateRange = dateBounds(allPoints);

// The average dataset (and its legend entry) is omitted entirely for events
// that have no average, such as Multi-Blind, where the data element is absent.
const datasets = [
    {
        label: SINGLE_LABEL,
        data: singleSeries,
        borderColor: SINGLE_COLOUR,
        backgroundColor: SINGLE_COLOUR,
    },
];
if (document.getElementById(AVERAGE_CHART_DATA_ELEMENT_ID)) {
    datasets.push({
        label: AVERAGE_LABEL,
        data: averageSeries,
        borderColor: AVERAGE_COLOUR,
        backgroundColor: AVERAGE_COLOUR,
    });
}

new Chart(canvas, {
    type: "line",
    data: { datasets },
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
                title: { display: true, text: resultAxisLabel },
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
