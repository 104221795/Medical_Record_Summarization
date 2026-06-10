import { TriangleAlert } from "lucide-react";

export default function ErrorState({ error }) {
  return (
    <div className="state error">
      <TriangleAlert aria-hidden="true" className="ui-icon state-icon" size={22} strokeWidth={2.2} />
      <div>
        <strong>Something went wrong</strong>
        <p>{error?.message || String(error)}</p>
      </div>
    </div>
  );
}
