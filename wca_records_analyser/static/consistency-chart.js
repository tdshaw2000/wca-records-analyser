const CONSISTENCY_CHART_DATA_ELEMENT_ID = "consistency-chart-data";
const CONSISTENCY_CANVAS_ELEMENT_ID = "consistency-progression";
const CONSISTENCY_LABEL = "Average ÷ single";
const CONSISTENCY_COLOUR = "#9333ea";
const CONSISTENCY_TIME_AXIS_LABEL = "Time →";
const CONSISTENCY_AXIS_LABEL = "average ÷ single (1.00 = perfectly consistent)";
const PERFECT_CONSISTENCY = 1;
const CONSISTENCY_AXIS_HEADROOM_FRACTION = 0.1;
const CONSISTENCY_MINIMUM_HEADROOM = 0.05;

const consistencyCanvas = document.getElementById(CONSISTENCY_CANVAS_ELEMENT_ID);
const consistencyDataElement = document.getElementById(
    CONSISTENCY_CHART_DATA_ELEMENT_ID,
);

if (consistencyCanvas && consistencyDataElement) {
    const consistencySeries = JSON.parse(consistencyDataElement.textContent);
    const ratios = consistencySeries.map((point) => point.y);
    const highestRatio = Math.max(...ratios);
    const headroom = Math.max(
        (highestRatio - PERFECT_CONSISTENCY) * CONSISTENCY_AXIS_HEADROOM_FRACTION,
        CONSISTENCY_MINIMUM_HEADROOM,
    );
    const dates = consistencySeries.map((point) => point.x).sort();

    new Chart(consistencyCanvas, {
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
                    title: { display: true, text: CONSISTENCY_TIME_AXIS_LABEL },
                    ticks: { display: false },
                    grid: { display: false },
                },
                y: {
                    min: PERFECT_CONSISTENCY,
                    max: highestRatio + headroom,
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
            },
        },
    });
}
