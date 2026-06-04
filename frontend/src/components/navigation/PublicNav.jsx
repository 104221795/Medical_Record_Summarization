import { Link, useLocation } from "react-router-dom";
import { brandAssets } from "../../assets/branding.js";

const publicLinks = [
  { label: "Home", path: "/" },
  { label: "About", path: "/about" },
  { label: "Sign In", path: "/login" },
  { label: "Sign Up", path: "/signup" },
];

export default function PublicNav() {
  const location = useLocation();
  return (
    <nav className="public-nav">
      <Link className="public-brand" to="/">
        <img src={brandAssets.logo} alt="" />
        <span>Medical Record Summarization</span>
      </Link>
      <div>
        {publicLinks.map((link) => (
          <Link
            key={link.path}
            className={isActivePublicLink(location.pathname, link.path) ? "active" : ""}
            to={link.path}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

function isActivePublicLink(pathname, path) {
  if (path === "/") return pathname === "/";
  return pathname === path;
}
