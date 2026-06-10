import { Stethoscope } from "lucide-react";

export default function PageHeader({ eyebrow, title, description, actions, icon: Icon = Stethoscope }) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        <div className="page-header-icon">
          <Icon aria-hidden="true" className="ui-icon" size={22} strokeWidth={2.2} />
        </div>
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  );
}
