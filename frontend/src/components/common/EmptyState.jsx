export default function EmptyState({ title = "Nothing here yet", message = "Load data or adjust the filters." }) {
  return <div className="state empty"><strong>{title}</strong><p>{message}</p></div>;
}
