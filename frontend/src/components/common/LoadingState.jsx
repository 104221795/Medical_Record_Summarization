import { LoaderCircle } from "lucide-react";

export default function LoadingState({ label = "Loading..." }) {
  return (
    <div className="state loading">
      <LoaderCircle aria-hidden="true" className="ui-icon loading-spinner" size={20} strokeWidth={2.2} />
      <span>{label}</span>
    </div>
  );
}
