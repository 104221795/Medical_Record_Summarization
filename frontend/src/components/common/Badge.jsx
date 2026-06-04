export default function Badge({ children, tone = "neutral", className = "" }) {
  return <span className={`badge ${tone} ${className}`.trim()}>{children}</span>;
}
