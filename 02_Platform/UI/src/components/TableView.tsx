
export type Row = Record<string, any>;

export type SpecialAction = {
    label: string; // "Edit" | "Copy" | etc.
    onClick: (row: Row) => void;
};

export interface TableViewProps {
    columns: { key: string; label: string }[];
    rows: Row[];
    onDelete?: (row: Row) => void;
    special?: SpecialAction;
    title?: string;
}

export function TableView(props: TableViewProps) {
    const { columns, rows, onDelete, special, title } = props;

    return (
        <div style={{ padding: 16, fontFamily: "system-ui, sans-serif" }}>
            {title && <h2 style={{ marginTop: 0 }}>{title}</h2>}

            <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                        <tr>
                            {columns.map((c) => (
                                <th
                                    key={c.key}
                                    style={{
                                        textAlign: "left",
                                        padding: "10px 8px",
                                        borderBottom: "1px solid #ddd",
                                        whiteSpace: "nowrap",
                                    }}
                                >
                                    {c.label}
                                </th>
                            ))}
                            {(special || onDelete) && (
                                <th
                                    style={{
                                        textAlign: "right",
                                        padding: "10px 8px",
                                        borderBottom: "1px solid #ddd",
                                        whiteSpace: "nowrap",
                                    }}
                                >
                                    Actions
                                </th>
                            )}
                        </tr>
                    </thead>

                    <tbody>
                        {rows.length === 0 ? (
                            <tr>
                                <td colSpan={columns.length + (special || onDelete ? 1 : 0)} style={{ padding: 12, color: "#666" }}>
                                    No items found
                                </td>
                            </tr>
                        ) : (
                            rows.map((row, i) => (
                                <tr key={row.workout_id || row.id || i}>
                                    {columns.map((c) => (
                                        <td
                                            key={c.key}
                                            style={{
                                                padding: "10px 8px",
                                                borderBottom: "1px solid #f0f0f0",
                                                whiteSpace: "nowrap",
                                            }}
                                        >
                                            {String(row[c.key] ?? "")}
                                        </td>
                                    ))}

                                    {(special || onDelete) && (
                                        <td
                                            style={{
                                                padding: "10px 8px",
                                                borderBottom: "1px solid #f0f0f0",
                                                textAlign: "right",
                                                whiteSpace: "nowrap",
                                            }}
                                        >
                                            {special && (
                                                <button onClick={() => special.onClick(row)} style={{ marginRight: 8 }}>
                                                    {special.label}
                                                </button>
                                            )}
                                            {onDelete && <button onClick={() => onDelete(row)}>Delete</button>}
                                        </td>
                                    )}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
