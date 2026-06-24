// Wrapped in an IIFE: this script and records-chart.js are both classic scripts
// on the same page and share global scope, so top-level names (ZOOM_AXIS_MODE,
// pointsFramingWindow, ...) would collide and throw a redeclaration SyntaxError.
(function () {
    const CONSISTENCY_CHART_DATA_ELEMENT_ID = "consistency-chart-data";
    const CONSISTENCY_CANVAS_ELEMENT_ID = "consistency-progression";
    const CONSISTENCY_RESET_ZOOM_BUTTON_ELEMENT_ID = "consistency-reset-zoom";
    const CONSISTENCY_LABEL = "Average ÷ single";
    const CONSISTENCY_COLOUR = "#9333ea";
    const CONSISTENCY_TIME_AXIS_LABEL = "Time →";
    const CONSISTENCY_AXIS_LABEL =
        "average ÷ single (1.00 = perfectly consistent)";
    const PERFECT_CONSISTENCY = 1;
    const CONSISTENCY_AXIS_HEADROOM_FRACTION = 0.1;
    const CONSISTENCY_MINIMUM_HEADROOM = 0.05;
    // Zoom and pan are constrained to the time axis; the ratio axis is rescaled
    // by hand (see rescaleConsistencyAxisToWindow) to fit whatever period is in
    // view.
    const ZOOM_AXIS_MODE = "x";
    const NO_ANIMATION_UPDATE_MODE = "none";

    // The ratio axis is anchored at the perfect-consistency baseline and given
    // headroom above the highest visible ratio, so the 1.00 reference line stays
    // in view and a zoomed-in window fills the space up to its own peak.
    function consistencyBounds(points) {
        const highestRatio = Math.max(...points.map((point) => point.y));
        const headroom = Math.max(
            (highestRatio - PERFECT_CONSISTENCY) *
                CONSISTENCY_AXIS_HEADROOM_FRACTION,
            CONSISTENCY_MINIMUM_HEADROOM,
        );
        return { min: PERFECT_CONSISTENCY, max: highestRatio + headroom };
    }

    function applyConsistencyBounds(chart, bounds) {
        const ratioAxis = chart.options.scales.y;
        ratioAxis.min = bounds.min;
        ratioAxis.max = bounds.max;
    }

    // The points that frame a time window: those inside it, plus the nearest
    // point on each side. The bracketing points matter because a connecting line
    // can cross the window even when no vertex falls inside it — without them,
    // zooming into the gap between two records finds nothing and the axis snaps
    // back to the full-career scale.
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

    const consistencyCanvas = document.getElementById(
        CONSISTENCY_CANVAS_ELEMENT_ID,
    );
    const consistencyDataElement = document.getElementById(
        CONSISTENCY_CHART_DATA_ELEMENT_ID,
    );
    const consistencyResetZoomButton = document.getElementById(
        CONSISTENCY_RESET_ZOOM_BUTTON_ELEMENT_ID,
    );

    if (consistencyCanvas && consistencyDataElement) {
        const consistencySeries = JSON.parse(consistencyDataElement.textContent);
        const consistencyRange = consistencyBounds(consistencySeries);
        const dates = consistencySeries.map((point) => point.x).sort();

        // After a zoom or pan, refit the ratio axis to whatever is visible in
        // the time window so a zoomed-in period fills the vertical space rather
        // than being squashed against the full-career scale.
        const rescaleConsistencyAxisToWindow = (chart) => {
            const timeAxis = chart.scales.x;
            const framingPoints = pointsFramingWindow(
                consistencySeries,
                timeAxis.min,
                timeAxis.max,
            );
            if (consistencyResetZoomButton) {
                consistencyResetZoomButton.hidden = false;
            }
            // Nothing in view: leave the axis as it is rather than jumping to a
            // meaningless scale.
            if (framingPoints.length) {
                applyConsistencyBounds(chart, consistencyBounds(framingPoints));
            }
            chart.update(NO_ANIMATION_UPDATE_MODE);
        };

        const consistencyChart = new Chart(consistencyCanvas, {
            type: "line",
            data: {
                datasets: [
                    {
                        label: CONSISTENCY_LABEL,
                        data: consistencySeries,
                        borderColor: CONSISTENCY_COLOUR,
                        backgroundColor: CONSISTENCY_COLOUR,
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
                        title: {
                            display: true,
                            text: CONSISTENCY_TIME_AXIS_LABEL,
                        },
                        ticks: { display: false },
                        grid: { display: false },
                    },
                    y: {
                        min: consistencyRange.min,
                        max: consistencyRange.max,
                        title: { display: true, text: CONSISTENCY_AXIS_LABEL },
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
                    // pinch (mobile) zoom. All restricted to the time axis, with
                    // the ratio axis rescaled to the window after each gesture.
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: ZOOM_AXIS_MODE,
                            onPan: ({ chart }) =>
                                rescaleConsistencyAxisToWindow(chart),
                        },
                        zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: ZOOM_AXIS_MODE,
                            onZoom: ({ chart }) =>
                                rescaleConsistencyAxisToWindow(chart),
                        },
                    },
                },
            },
        });

        if (consistencyResetZoomButton) {
            consistencyResetZoomButton.addEventListener("click", () => {
                consistencyChart.resetZoom();
                applyConsistencyBounds(consistencyChart, consistencyRange);
                consistencyChart.update(NO_ANIMATION_UPDATE_MODE);
                consistencyResetZoomButton.hidden = true;
            });
        }
    }
})();
