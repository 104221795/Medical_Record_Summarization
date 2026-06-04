import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../../components/common/Button.jsx";
import Card from "../../components/common/Card.jsx";
import PublicNav from "../../components/navigation/PublicNav.jsx";
import { brandAssets } from "../../assets/branding.js";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  return (
    <main className="login-page auth-page">
      <PublicNav />
      <Card title="Reset Access" className="auth-card">
        <img className="login-logo" src={brandAssets.logo} alt="Medical Record Summarization logo" />
        <p className="muted">Demo reset flow. In production this would send a governed password reset email.</p>
        <label className="field">
          <span>Email</span>
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="doctor@example.org" />
        </label>
        {submitted && <p className="warning-line">If this were a configured production tenant, reset instructions would be sent after identity checks.</p>}
        <div className="public-actions">
          <Button disabled={!email} onClick={() => setSubmitted(true)}>Request Reset</Button>
          <Link to="/login"><Button variant="secondary">Back to Login</Button></Link>
        </div>
      </Card>
    </main>
  );
}
