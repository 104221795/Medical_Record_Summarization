import { Route, Routes } from "react-router-dom";
import AdminLayout from "../layouts/AdminLayout.jsx";
import DoctorLayout from "../layouts/DoctorLayout.jsx";
import ProtectedRoute from "./ProtectedRoute.jsx";
import HomePage from "../pages/shared/HomePage.jsx";
import AboutPage from "../pages/shared/AboutPage.jsx";
import LoginPage from "../pages/shared/LoginPage.jsx";
import SignupPage from "../pages/shared/SignupPage.jsx";
import ForgotPasswordPage from "../pages/shared/ForgotPasswordPage.jsx";
import UserGuidePage from "../pages/shared/UserGuidePage.jsx";
import NotFoundPage from "../pages/shared/NotFoundPage.jsx";
import DoctorDashboardPage from "../pages/doctor/DoctorDashboardPage.jsx";
import PatientListPage from "../pages/doctor/PatientListPage.jsx";
import PatientDetailPage from "../pages/doctor/PatientDetailPage.jsx";
import DoctorGenerateSummaryPage from "../pages/doctor/DoctorGenerateSummaryPage.jsx";
import DoctorReviewEvidencePage from "../pages/doctor/DoctorReviewEvidencePage.jsx";
import DoctorPatientHistoryPage from "../pages/doctor/DoctorPatientHistoryPage.jsx";
import DoctorAuditHistoryPage from "../pages/doctor/DoctorAuditHistoryPage.jsx";
import AdminDashboardPage from "../pages/admin/AdminDashboardPage.jsx";
import DatasetGovernancePage from "../pages/admin/DatasetGovernancePage.jsx";
import EvaluationDashboardPage from "../pages/admin/EvaluationDashboardPage.jsx";
import BenchmarkResultsPage from "../pages/admin/BenchmarkResultsPage.jsx";
import FlowComparisonPage from "../pages/admin/FlowComparisonPage.jsx";
import RagBestModelsPage from "../pages/admin/RagBestModelsPage.jsx";
import AuditLogPage from "../pages/admin/AuditLogPage.jsx";
import SettingsPage from "../pages/admin/SettingsPage.jsx";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/doctor" element={<ProtectedRoute role="doctor"><DoctorLayout /></ProtectedRoute>}>
        <Route index element={<DoctorDashboardPage />} />
        <Route path="dashboard" element={<DoctorDashboardPage />} />
        <Route path="patients" element={<PatientListPage />} />
        <Route path="patients/:patientId" element={<PatientDetailPage />} />
        <Route path="patients/:patientId/generate-summary" element={<DoctorGenerateSummaryPage />} />
        <Route path="patients/:patientId/summary-workspace" element={<PatientDetailPage />} />
        <Route path="patients/:patientId/review" element={<PatientDetailPage />} />
        <Route path="generate-summary" element={<DoctorGenerateSummaryPage />} />
        <Route path="summary-workspace" element={<DoctorReviewEvidencePage />} />
        <Route path="review" element={<DoctorReviewEvidencePage />} />
        <Route path="review/:summaryId" element={<DoctorReviewEvidencePage />} />
        <Route path="patient-history" element={<DoctorPatientHistoryPage />} />
        <Route path="audit-history" element={<DoctorAuditHistoryPage />} />
        <Route path="audit" element={<DoctorAuditHistoryPage />} />
        <Route path="user-guide" element={<UserGuidePage />} />
        <Route path="guide" element={<UserGuidePage />} />
      </Route>
      <Route path="/admin" element={<ProtectedRoute role="admin"><AdminLayout /></ProtectedRoute>}>
        <Route index element={<AdminDashboardPage />} />
        <Route path="dashboard" element={<AdminDashboardPage />} />
        <Route path="datasets" element={<DatasetGovernancePage />} />
        <Route path="evaluation" element={<EvaluationDashboardPage />} />
        <Route path="evaluation/benchmark" element={<BenchmarkResultsPage />} />
        <Route path="evaluation/flow-comparison" element={<FlowComparisonPage />} />
        <Route path="evaluation/rag-best-models" element={<RagBestModelsPage />} />
        <Route path="audit" element={<AuditLogPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="guide" element={<UserGuidePage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
