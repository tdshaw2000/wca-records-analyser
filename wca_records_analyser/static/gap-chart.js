// Wrapped in an IIFE: this script shares global scope with the other classic
// chart scripts on the page, so top-level names would collide.
(function () {
    const GAP_CHART_DATA_ELEMENT_ID = "gap-chart-data";
    const GAP_CANVAS_ELEMENT_ID = "gap-progression";
    const GAP_LABEL = "Average − single";
    const GAP_COLOUR = "#ea580c";
    const TIME_PROGRESSION_AXIS_LABEL = "Time →";
    const GAP_AXIS_LABEL = "average − single (0 = identical)";
    const CENTISECONDS_PER_SECOND = 100;
    const SECONDS_PER_MINUTE = 60;
    const SECONDS_PAD = 2;
    const MOVES_UNIT = "moves";
    const AXIS_HEADROOM_FRACTION = 0.1;
    const AXIS_BASELINE = 0;

    const canvas = document.getElementById(GAP_CANVAS_ELEMENT_ID);
    const dataElement = document.getElementById(GAP_CHART_DATA_ELEMENT_ID);
    if (!canvas || !dataElement) {
        return;
    }

    const resultUnit = canvas.dataset.resultUnit;
    const series = JSON.parse(dataElement.textContent);
    const values = series.map((point) => point.y);
    const highest = Math.max(...values);
    const headroom = highest * AXIS_HEADROOM_FRACTION;
    const dates = series.map((point) => point.x).sort();

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

    new Chart(canvas, {
        type: "line",
        data: {
            datasets: [
                {
                    label: GAP_LABEL,
                    data: series,
                    borderColor: GAP_COLOUR,
                    backgroundColor: GAP_COLOUR,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: "time",
                    min: dates[0],
                    max: dates[dates.length - 1],
                    title: { display: true, text: TIME_PROGRESSION_AXIS_LABEL },
                    ticks: { display: false },
                    grid: { display: false },
                },
                y: {
                    min: AXIS_BASELINE,
                    max: highest + headroom,
                    title: { display: true, text: GAP_AXIS_LABEL },
                    ticks: { callback: (value) => formatAxisTick(value) },
                },
            },
            plugins: {
                legend: { display: false },
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
