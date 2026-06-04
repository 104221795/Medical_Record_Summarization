import { Outlet } from "react-router-dom";
import Breadcrumbs from "../components/navigation/Breadcrumbs.jsx";
import Sidebar from "../components/navigation/Sidebar.jsx";
import Topbar from "../components/navigation/Topbar.jsx";

export default function MainLayout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-surface">
        <Topbar />
        <Breadcrumbs />
        <main className="page"><Outlet /></main>
      </div>
    </div>
  );
}
