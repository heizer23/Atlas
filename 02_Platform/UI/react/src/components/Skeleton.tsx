// Animated loading placeholder — 3 rows, variable-width cells
export default function Skeleton() {
  const widths = [
    ["40%", "20%", "15%", "25%"],
    ["55%", "15%", "20%", "10%"],
    ["30%", "25%", "18%", "27%"],
  ];

  return (
    <div className="skeleton">
      {widths.map((row, i) => (
        <div key={i} className="skeleton-row">
          {row.map((w, j) => (
            <div
              key={j}
              className="skeleton-cell"
              style={{ width: w, flex: "0 0 auto" }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
