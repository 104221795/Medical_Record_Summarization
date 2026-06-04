import { Link } from "react-router-dom";
import EmptyState from "../../components/common/EmptyState.jsx";

export default function NotFoundPage() {
  return <EmptyState title="Page not found" message={<Link to="/doctor">Return to workspace</Link>} />;
}
