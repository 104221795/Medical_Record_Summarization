export default function LoadingState({ label = "Loading..." }) {
  return <div className="state loading"><span className="loading-dot" />{label}</div>;
}
