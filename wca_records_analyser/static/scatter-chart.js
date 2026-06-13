// Wrapped in an IIFE: this script and records-chart.js are both classic scripts
// on the same page and share global scope, so top-level names would collide.
(function () {
    const SINGLE_SCATTER_DATA_ELEMENT_ID = "all-singles-scatter-data";
    const AVERAGE_SCATTER_DATA_ELEMENT_ID = "all-averages-scatter-data";
    const SCATTER_CANVAS_ELEMENT_ID = "all-results-scatter";
    const SINGLE_LABEL = "Single";
    const AVERAGE_LABEL = "Average";
    const SINGLE_COLOUR = "#2563eb";
    const AVERAGE_COLOUR = "#449964";
    const TIME_PROGRESSION_AXIS_LABEL = "Time →";
    const RESULT_AXIS_LABEL = "Result";
    const CENTISECONDS_PER_SECOND = 100;
    const SECONDS_PER_MINUTE = 60;
    const SECONDS_PAD = 2;
    const RESULT_AXIS_PADDING_FRACTION = 0.05;
    const FADED_LEGEND_COLOUR = "rgba(31, 41, 51, 0.35)";
    const MOVES_UNIT = "moves";
    const POINT_RADIUS = 3;
    const POINT_HOVER_RADIUS = 5;

    const canvas = document.getElementById(SCATTER_CANVAS_ELEMENT_ID);
    const singleDataElement = document.getElementById(
        SINGLE_SCATTER_DATA_ELEMENT_ID,
    );
    const averageDataElement = document.getElementById(
        AVERAGE_SCATTER_DATA_ELEMENT_ID,
    );
    if (!canvas || (!singleDataElement && !averageDataElement)) {
        return;
    }

    const resultUnit = canvas.dataset.resultUnit;
    const singleSeries = singleDataElement
        ? JSON.parse(singleDataElement.textContent)
        : [];
    const averageSeries = averageDataElement
        ? JSON.parse(averageDataElement.textContent)
        : [];
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

    function fadeHiddenLegendLabels(chart) {
        const labels =
            Chart.defaults.plugins.legend.labels.generateLabels(chart);
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

    const resultRange = resultBounds(allPoints);
    const dateRange = dateBounds(allPoints);

    // Drawn as a line chart with the connecting line hidden: this reuses the
    // record chart's proven config, whereas Chart.js's scatter controller
    // mis-parses the string dates on a time axis and silently drops points.
    new Chart(canvas, {
        type: "line",
        data: {
            datasets: [
                {
                    label: SINGLE_LABEL,
                    data: singleSeries,
                    borderColor: SINGLE_COLOUR,
                    backgroundColor: SINGLE_COLOUR,
                    showLine: false,
                    pointRadius: POINT_RADIUS,
                    pointHoverRadius: POINT_HOVER_RADIUS,
                },
                {
                    label: AVERAGE_LABEL,
                    data: averageSeries,
                    borderColor: AVERAGE_COLOUR,
                    backgroundColor: AVERAGE_COLOUR,
                    showLine: false,
                    pointRadius: POINT_RADIUS,
                    pointHoverRadius: POINT_HOVER_RADIUS,
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
})();
