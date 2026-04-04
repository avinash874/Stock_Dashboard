export const defaultLineChartOptions = {
  responsive: true,
  plugins: {
    legend: { labels: { color: "#8b9bb4" } },
  },
  scales: {
    x: {
      ticks: { color: "#8b9bb4", maxTicksLimit: 10 },
      grid: { color: "#2d3a4d" },
    },
    y: {
      ticks: { color: "#8b9bb4" },
      grid: { color: "#2d3a4d" },
    },
  },
};

export function compareLineChartOptions() {
  return {
    ...defaultLineChartOptions,
    scales: {
      ...defaultLineChartOptions.scales,
      y: {
        ...defaultLineChartOptions.scales.y,
        title: { display: true, text: "Indexed to 100 at start", color: "#8b9bb4" },
      },
    },
  };
}
