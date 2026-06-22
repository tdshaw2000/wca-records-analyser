// Wrapped in an IIFE: this script and records-chart.js are both classic scripts
// on the same page and share global scope, so top-level names would collide.
(function () {
    const SINGLE_SCATTER_DATA_ELEMENT_ID = "all-singles-scatter-data";
    const AVERAGE_SCATTER_DATA_ELEMENT_ID = "all-averages-scatter-data";
    const BAND_DATA_ELEMENT_ID = "daily-range-data";
    const SCATTER_CANVAS_ELEMENT_ID = "all-results-scatter";
    const SINGLE_LABEL = "Single";
    const AVERAGE_LABEL = "Average";
    const BAND_LABEL = "Daily range";
    // Hidden helper dataset that the band fills down to; kept out of the legend so
    // a single "Daily range" entry toggles the whole band.
    const BAND_LOWER_BOUND_LABEL = "Daily range (fastest)";
    const SINGLE_COLOUR = "#2563eb";
    const AVERAGE_COLOUR = "#449964";
    // A translucent wash of the Single colour, so the band reads as the spread of
    // the singles it envelopes.
    const BAND_FILL_COLOUR = "rgba(37, 99, 235, 0.15)";
    const BAND_BORDER_COLOUR = "transparent";
    const BAND_BORDER_WIDTH = 0;
    const BAND_POINT_RADIUS = 0;
    const BAND_LOWER_BOUND_KEY = "lower";
    const BAND_UPPER_BOUND_KEY = "upper";
    const NO_DATASET_INDEX = -1;
    // The band sorts after the scatter entries so the legend reads Single,
    // Average, Daily range.
    const LEGEND_BAND_ORDER = 1;
    const LEGEND_SCATTER_ORDER = 0;
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
    // multiples (in centiseconds) so every tick formats to a clean, distinct
    // label; count steps follow the same 1-2-5 ladder for moves/points axes.
    const NICE_TIME_STEPS_CENTISECONDS = [
        100, 200, 500, 1000, 1500, 3000, 6000, 12000, 30000, 60000, 120000,
        300000, 600000, 1200000, 3000000,
    ];
    const NICE_COUNT_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
    const POINT_RADIUS = 3;
    const POINT_HOVER_RADIUS = 5;
    const RESET_ZOOM_BUTTON_ELEMENT_ID = "scatter-reset-zoom";
    // Zoom and pan are constrained to the time axis; the result axis is rescaled
    // by hand (see rescaleResultAxisToWindow) to fit whatever period is in view.
    const ZOOM_AXIS_MODE = "x";
    const NO_ANIMATION_UPDATE_MODE = "none";

    const canvas = document.getElementById(SCATTER_CANVAS_ELEMENT_ID);
    const singleDataElement = document.getElementById(
        SINGLE_SCATTER_DATA_ELEMENT_ID,
    );
    const averageDataElement = document.getElementById(
        AVERAGE_SCATTER_DATA_ELEMENT_ID,
    );
    const resetZoomButton = document.getElementById(
        RESET_ZOOM_BUTTON_ELEMENT_ID,
    );
    if (!canvas || (!singleDataElement && !averageDataElement)) {
        return;
    }

    const resultUnit = canvas.dataset.resultUnit;
    const resultAxisLabel =
        resultUnit === POINTS_UNIT ? POINTS_AXIS_LABEL : RESULT_AXIS_LABEL;
    const singleSeries = singleDataElement
        ? JSON.parse(singleDataElement.textContent)
        : [];
    const averageSeries = averageDataElement
        ? JSON.parse(averageDataElement.textContent)
        : [];
    const bandDataElement = document.getElementById(BAND_DATA_ELEMENT_ID);
    const bandBounds = bandDataElement
        ? JSON.parse(bandDataElement.textContent)
        : null;
    // Assigned when the band is built; the legend entry sits on the visible
    // (slowest) dataset, the helper (fastest) one it fills down to is hidden.
    let bandLegendDatasetIndex = NO_DATASET_INDEX;
    let bandHelperDatasetIndex = NO_DATASET_INDEX;
    const allPoints = [...singleSeries, ...averageSeries];

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

    // Snap padded bounds outward onto a nice tick step so every gridline lands
    // on a value that formats to a unique label.
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

    // After a zoom or pan, refit the result axis to only the points inside the
    // visible time window, so a zoomed-in period fills the vertical space rather
    // than being squashed against the full-career scale. Falls back to the whole
    // series when the window happens to contain no points.
    function rescaleResultAxisToWindow(chart) {
        const timeAxis = chart.scales.x;
        const pointsInWindow = allPoints.filter((point) => {
            const timestamp = new Date(point.x).getTime();
            return timestamp >= timeAxis.min && timestamp <= timeAxis.max;
        });
        const visiblePoints = pointsInWindow.length ? pointsInWindow : allPoints;
        applyResultBounds(chart, snapAxisBounds(resultBounds(visiblePoints)));
        if (resetZoomButton) {
            resetZoomButton.hidden = false;
        }
        chart.update(NO_ANIMATION_UPDATE_MODE);
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

    function legendOrder(label) {
        return label.datasetIndex === bandLegendDatasetIndex
            ? LEGEND_BAND_ORDER
            : LEGEND_SCATTER_ORDER;
    }

    // Drop the band's hidden helper entry, fade any toggled-off series, and keep
    // the band's single entry last so it reads Single, Average, Daily range.
    function buildLegendLabels(chart) {
        const labels = Chart.defaults.plugins.legend.labels
            .generateLabels(chart)
            .filter((label) => label.datasetIndex !== bandHelperDatasetIndex);
        for (const label of labels) {
            if (!chart.isDatasetVisible(label.datasetIndex)) {
                label.hidden = false;
                label.fontColor = FADED_LEGEND_COLOUR;
                label.fillStyle = FADED_LEGEND_COLOUR;
                label.strokeStyle = FADED_LEGEND_COLOUR;
            }
        }
        labels.sort((first, second) => legendOrder(first) - legendOrder(second));
        return labels;
    }

    // Toggling the band's legend entry hides or shows both of its bounds together,
    // so the shaded area appears and disappears as one.
    function toggleLegendDataset(event, legendItem, legend) {
        const chart = legend.chart;
        const datasetIndex = legendItem.datasetIndex;
        const nowVisible = !chart.isDatasetVisible(datasetIndex);
        chart.setDatasetVisibility(datasetIndex, nowVisible);
        if (
            datasetIndex === bandLegendDatasetIndex &&
            bandHelperDatasetIndex !== NO_DATASET_INDEX
        ) {
            chart.setDatasetVisibility(bandHelperDatasetIndex, nowVisible);
        }
        chart.update();
    }

    const resultRange = snapAxisBounds(resultBounds(allPoints));
    const dateRange = dateBounds(allPoints);

    const datasets = [];
    // The band's two bounds go in first so they are drawn behind the scatter
    // points; the slowest bound fills down to the fastest one to shade the area.
    // It is absent for events without a band (such as Multi-Blind).
    if (bandBounds) {
        bandHelperDatasetIndex = datasets.length;
        datasets.push({
            label: BAND_LOWER_BOUND_LABEL,
            data: bandBounds[BAND_LOWER_BOUND_KEY],
            borderColor: BAND_BORDER_COLOUR,
            borderWidth: BAND_BORDER_WIDTH,
            backgroundColor: BAND_FILL_COLOUR,
            pointRadius: BAND_POINT_RADIUS,
            pointHoverRadius: BAND_POINT_RADIUS,
            fill: false,
        });
        bandLegendDatasetIndex = datasets.length;
        datasets.push({
            label: BAND_LABEL,
            data: bandBounds[BAND_UPPER_BOUND_KEY],
            borderColor: BAND_BORDER_COLOUR,
            borderWidth: BAND_BORDER_WIDTH,
            backgroundColor: BAND_FILL_COLOUR,
            pointRadius: BAND_POINT_RADIUS,
            pointHoverRadius: BAND_POINT_RADIUS,
            fill: bandHelperDatasetIndex,
        });
    }
    datasets.push({
        label: SINGLE_LABEL,
        data: singleSeries,
        borderColor: SINGLE_COLOUR,
        backgroundColor: SINGLE_COLOUR,
        showLine: false,
        pointRadius: POINT_RADIUS,
        pointHoverRadius: POINT_HOVER_RADIUS,
    });
    // The average dataset (and its legend entry) is omitted entirely for events
    // that have no average, such as Multi-Blind, where the data element is absent.
    if (averageDataElement) {
        datasets.push({
            label: AVERAGE_LABEL,
            data: averageSeries,
            borderColor: AVERAGE_COLOUR,
            backgroundColor: AVERAGE_COLOUR,
            showLine: false,
            pointRadius: POINT_RADIUS,
            pointHoverRadius: POINT_HOVER_RADIUS,
        });
    }

    // Drawn as a line chart with the connecting line hidden: this reuses the
    // record chart's proven config, whereas Chart.js's scatter controller
    // mis-parses the string dates on a time axis and silently drops points.
    const scatterChart = new Chart(canvas, {
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
                    onClick: toggleLegendDataset,
                    labels: { generateLabels: buildLegendLabels },
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
            scatterChart.resetZoom();
            applyResultBounds(scatterChart, resultRange);
            scatterChart.update(NO_ANIMATION_UPDATE_MODE);
            resetZoomButton.hidden = true;
        });
    }
})();
