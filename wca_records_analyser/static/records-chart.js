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
const TARGET_AXIS_TICK_COUNT = 6;
// Tick steps the y axis is allowed to snap to. Time steps are whole-second
// multiples (in centiseconds) so every tick formats to a clean, distinct label;
// count steps follow the same 1-2-5 ladder for moves/points axes. Letting
// Chart.js auto-pick sub-second steps and then rounding to whole seconds made
// adjacent ticks collapse to identical labels (two "10"s, two "15"s).
const NICE_TIME_STEPS_CENTISECONDS = [
    100, 200, 500, 1000, 1500, 3000, 6000, 12000, 30000, 60000, 120000, 300000,
    600000, 1200000, 3000000,
];
const NICE_COUNT_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
const RESET_ZOOM_BUTTON_ELEMENT_ID = "record-reset-zoom";
// Zoom and pan are constrained to the time axis; the result axis is rescaled by
// hand (see rescaleResultAxisToWindow) to fit whatever period is in view.
const ZOOM_AXIS_MODE = "x";
const NO_ANIMATION_UPDATE_MODE = "none";

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

// Snap padded bounds outward onto a nice tick step so every gridline lands on a
// value that formats to a unique label.
function snapAxisBounds(bounds) {
    const isCountUnit =
        resultUnit === MOVES_UNIT || resultUnit === POINTS_UNIT;
    const niceSteps = isCountUnit
        ? NICE_COUNT_STEPS
        : NICE_TIME_STEPS_CENTISECONDS;
    const targetStep = (bounds.max - bounds.min) / TARGET_AXIS_TICK_COUNT;
    const step =
        niceSteps.find((candidate) => candidate >= targetStep) ??
        niceSteps[niceSteps.length - 1];
    return {
        min: Math.max(0, Math.floor(bounds.min / step) * step),
        max: Math.ceil(bounds.max / step) * step,
        step,
    };
}

function applyResultBounds(chart, bounds) {
    const resultAxis = chart.options.scales.y;
    resultAxis.min = bounds.min;
    resultAxis.max = bounds.max;
    resultAxis.ticks.stepSize = bounds.step;
}

// The points that frame a time window for one series: those inside it, plus the
// nearest point on each side. The bracketing points matter because a connecting
// line can cross the window even when no vertex falls inside it — without them,
// zooming into the gap between two records finds nothing and the axis snaps back
// to the full-career scale.
function pointsFramingWindow(series, windowStart, windowEnd) {
    const framing = [];
    let nearestBefore = null;
    let nearestAfter = null;
    for (const point of series) {
        const timestamp = new Date(point.x).getTime();
        if (timestamp < windowStart) {
            if (
                !nearestBefore ||
                timestamp > new Date(nearestBefore.x).getTime()
            ) {
                nearestBefore = point;
            }
        } else if (timestamp > windowEnd) {
            if (
                !nearestAfter ||
                timestamp < new Date(nearestAfter.x).getTime()
            ) {
                nearestAfter = point;
            }
        } else {
            framing.push(point);
        }
    }
    if (nearestBefore) {
        framing.push(nearestBefore);
    }
    if (nearestAfter) {
        framing.push(nearestAfter);
    }
    return framing;
}

// After a zoom or pan, refit the result axis to whatever is visible in the time
// window — both record progressions — so a zoomed-in period fills the vertical
// space rather than being squashed against the full-career scale.
function rescaleResultAxisToWindow(chart) {
    const timeAxis = chart.scales.x;
    const framingPoints = [singleSeries, averageSeries].flatMap((series) =>
        pointsFramingWindow(series, timeAxis.min, timeAxis.max),
    );
    if (resetZoomButton) {
        resetZoomButton.hidden = false;
    }
    // Nothing in view (no data at all): leave the axis as it is rather than
    // jumping to a meaningless scale.
    if (framingPoints.length) {
        applyResultBounds(chart, snapAxisBounds(resultBounds(framingPoints)));
    }
    chart.update(NO_ANIMATION_UPDATE_MODE);
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
const resetZoomButton = document.getElementById(RESET_ZOOM_BUTTON_ELEMENT_ID);
const resultUnit = canvas.dataset.resultUnit;
const resultAxisLabel =
    resultUnit === POINTS_UNIT ? POINTS_AXIS_LABEL : RESULT_AXIS_LABEL;
const singleSeries = readSeries(SINGLE_CHART_DATA_ELEMENT_ID);
const averageSeries = readSeries(AVERAGE_CHART_DATA_ELEMENT_ID);
const allPoints = [...singleSeries, ...averageSeries];
const resultRange = snapAxisBounds(resultBounds(allPoints));
const dateRange = dateBounds(allPoints);

// The average dataset (and its legend entry) is omitted entirely for events that
// have no average, such as Multi-Blind, where the data element is absent.
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

const recordChart = new Chart(canvas, {
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
                ticks: {
                    stepSize: resultRange.step,
                    callback: (value) => formatAxisTick(value),
                },
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
            // Drag pans on both desktop and touch; wheel (desktop) and pinch
            // (mobile) zoom. All restricted to the time axis, with the result
            // axis rescaled to the window after each gesture.
            zoom: {
                pan: {
                    enabled: true,
                    mode: ZOOM_AXIS_MODE,
                    onPan: ({ chart }) => rescaleResultAxisToWindow(chart),
                },
                zoom: {
                    wheel: { enabled: true },
                    pinch: { enabled: true },
                    mode: ZOOM_AXIS_MODE,
                    onZoom: ({ chart }) => rescaleResultAxisToWindow(chart),
                },
            },
        },
    },
});

if (resetZoomButton) {
    resetZoomButton.addEventListener("click", () => {
        recordChart.resetZoom();
        applyResultBounds(recordChart, resultRange);
        recordChart.update(NO_ANIMATION_UPDATE_MODE);
        resetZoomButton.hidden = true;
    });
}
