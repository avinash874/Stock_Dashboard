import { Line } from "react-chartjs-2";

export function CompareLineChart({ chartData, options }) {
  return (
    <div className="mt-4 h-72">
      <Line data={chartData} options={options} />
    </div>
  );
}
