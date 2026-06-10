import { PanelTop } from "lucide-react";

export default function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          {title && (
            <h2>
              <PanelTop aria-hidden="true" className="ui-icon card-title-icon" size={17} strokeWidth={2.2} />
              <span>{title}</span>
            </h2>
          )}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}
