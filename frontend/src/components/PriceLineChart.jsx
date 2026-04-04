import { Line } from "react-chartjs-2";

export function PriceLineChart({ labels, datasets, chartKey, options }) {
  return (
    <div className="mt-4 h-72">
      <Line key={chartKey} data={{ labels, datasets }} options={options} />
    </div>
  );
}
