export default function Button({ children, variant = "primary", className = "", icon: Icon, iconPosition = "left", ...props }) {
  return (
    <button className={`btn ${variant} ${Icon ? "with-icon" : ""} ${className}`.trim()} {...props}>
      {Icon && iconPosition === "left" && <Icon aria-hidden="true" className="ui-icon btn-icon" size={17} strokeWidth={2.3} />}
      <span>{children}</span>
      {Icon && iconPosition === "right" && <Icon aria-hidden="true" className="ui-icon btn-icon" size={17} strokeWidth={2.3} />}
    </button>
  );
}
