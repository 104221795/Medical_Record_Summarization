import { Inbox } from "lucide-react";

export default function EmptyState({ title = "Nothing here yet", message = "Load data or adjust the filters." }) {
  return (
    <div className="state empty">
      <Inbox aria-hidden="true" className="ui-icon state-icon" size={22} strokeWidth={2.2} />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}
