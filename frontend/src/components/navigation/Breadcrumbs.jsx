import { useLocation } from "react-router-dom";

export default function Breadcrumbs() {
  const location = useLocation();
  const parts = location.pathname.split("/").filter(Boolean);
  return <div className="breadcrumbs">{parts.map((part) => <span key={part}>{part.replaceAll("-", " ")}</span>)}</div>;
}
