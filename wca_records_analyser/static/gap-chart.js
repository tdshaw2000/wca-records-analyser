// Wrapped in an IIFE: this script shares global scope with the other classic
// chart scripts on the page, so top-level names would collide.
(function () {
    const GAP_CHART_DATA_ELEMENT_ID = "gap-chart-data";
    const GAP_CANVAS_ELEMENT_ID = "gap-progression";
    const GAP_RESET_ZOOM_BUTTON_ELEMENT_ID = "gap-reset-zoom";
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
    const TARGET_AXIS_TICK_COUNT = 6;
    // Tick steps the y axis is allowed to snap to. Time steps are whole-second
    // multiples (in centiseconds) so every tick formats to a clean, distinct
    // label; count steps follow the same 1-2-5 ladder for the moves axis.
    // Without snapping, Chart.js picked sub-second steps and rounding to whole
    // seconds made adjacent ticks collapse to identical labels.
    const NICE_TIME_STEPS_CENTISECONDS = [
        100, 200, 500, 1000, 1500, 3000, 6000, 12000, 30000, 60000, 120000,
        300000, 600000, 1200000, 3000000,
    ];
    const NICE_COUNT_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
    // Zoom and pan are constrained to the time axis; the gap axis is rescaled by
    // hand (see rescaleGapAxisToWindow) to fit whatever period is in view.
    const ZOOM_AXIS_MODE = "x";
    const NO_ANIMATION_UPDATE_MODE = "none";

    const canvas = document.getElementById(GAP_CANVAS_ELEMENT_ID);
    const dataElement = document.getElementById(GAP_CHART_DATA_ELEMENT_ID);
    const resetZoomButton = document.getElementById(
        GAP_RESET_ZOOM_BUTTON_ELEMENT_ID,
    );
    if (!canvas || !dataElement) {
        return;
    }

    const resultUnit = canvas.dataset.resultUnit;
    const series = JSON.parse(dataElement.textContent);
    const values = series.map((point) => point.y);
    const highest = Math.max(...values);
    const headroom = highest * AXIS_HEADROOM_FRACTION;
    const dates = series.map((point) => point.x).sort();

    // Snap padded bounds outward onto a nice tick step so every gridline lands
    // on a value that formats to a unique label.
    function snapAxisBounds(bounds) {
        const niceSteps =
            resultUnit === MOVES_UNIT
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

    const resultRange = snapAxisBounds({
        min: AXIS_BASELINE,
        max: highest + headroom,
    });

    function applyResultBounds(chart, bounds) {
        const resultAxis = chart.options.scales.y;
        resultAxis.min = bounds.min;
        resultAxis.max = bounds.max;
        resultAxis.ticks.stepSize = bounds.step;
    }

    // The points that frame a time window: those inside it, plus the nearest
    // point on each side. The bracketing points matter because the connecting
    // line can cross the window even when no vertex falls inside it — without
    // them, zooming into the gap between two records finds nothing and the axis
    // snaps back to the full-career scale.
    function pointsFramingWindow(points, windowStart, windowEnd) {
        const framing = [];
        let nearestBefore = null;
        let nearestAfter = null;
        for (const point of points) {
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

    // After a zoom or pan, refit the gap axis to whatever is visible in the time
    // window — keeping the zero baseline — so a zoomed-in period fills the
    // vertical space rather than being squashed against the full-career scale.
    function rescaleGapAxisToWindow(chart) {
        const timeAxis = chart.scales.x;
        const framingPoints = pointsFramingWindow(
            series,
            timeAxis.min,
            timeAxis.max,
        );
        if (resetZoomButton) {
            resetZoomButton.hidden = false;
        }
        // Nothing in view: leave the axis as it is rather than jumping to a
        // meaningless scale.
        if (framingPoints.length) {
            const highestInWindow = Math.max(
                ...framingPoints.map((point) => point.y),
            );
            applyResultBounds(
                chart,
                snapAxisBounds({
                    min: AXIS_BASELINE,
                    max: highestInWindow + highestInWindow * AXIS_HEADROOM_FRACTION,
                }),
            );
        }
        chart.update(NO_ANIMATION_UPDATE_MODE);
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

    const gapChart = new Chart(canvas, {
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
                    min: resultRange.min,
                    max: resultRange.max,
                    title: { display: true, text: GAP_AXIS_LABEL },
                    ticks: {
                        stepSize: resultRange.step,
                        callback: (value) => formatAxisTick(value),
                    },
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
                // Drag pans on both desktop and touch; wheel (desktop) and
                // pinch (mobile) zoom. All restricted to the time axis, with the
                // gap axis rescaled to the window after each gesture.
                zoom: {
                    pan: {
                        enabled: true,
                        mode: ZOOM_AXIS_MODE,
                        onPan: ({ chart }) => rescaleGapAxisToWindow(chart),
                    },
                    zoom: {
                        wheel: { enabled: true },
                        pinch: { enabled: true },
                        mode: ZOOM_AXIS_MODE,
                        onZoom: ({ chart }) => rescaleGapAxisToWindow(chart),
                    },
                },
            },
        },
    });

    if (resetZoomButton) {
        resetZoomButton.addEventListener("click", () => {
            gapChart.resetZoom();
            applyResultBounds(gapChart, resultRange);
            gapChart.update(NO_ANIMATION_UPDATE_MODE);
            resetZoomButton.hidden = true;
        });
    }
})();
