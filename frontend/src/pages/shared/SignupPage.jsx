import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound, ShieldCheck, Sparkles, UserPlus } from "lucide-react";
import Button from "../../components/common/Button.jsx";
import Card from "../../components/common/Card.jsx";
import PublicNav from "../../components/navigation/PublicNav.jsx";
import { brandAssets } from "../../assets/branding.js";
import { authApi } from "../../services/authApi.js";
import { useRole } from "../../hooks/useRole.js";
import { generatePassword, passwordChecks, passwordStrength, validateEmail } from "../../utils/authValidation.js";

export default function SignupPage() {
  const navigate = useNavigate();
  const { login } = useRole();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
    role: "doctor",
    tenant_id: "sandbox",
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const strength = passwordStrength(form.password);
  const checks = passwordChecks(form.password);
  const emailValid = validateEmail(form.email);
  const passwordsMatch = form.password && form.password === form.confirm_password;
  const canSubmit = form.full_name.trim().length >= 2 && emailValid && passwordsMatch && strength.score === 5;

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const autoGeneratePassword = () => {
    const next = generatePassword();
    setForm((current) => ({ ...current, password: next, confirm_password: next }));
  };
  const submit = async () => {
    if (!canSubmit) {
      setError("Please complete required fields and use a strong matching password.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await authApi.signup(form);
      login({
        role: result.role,
        userId: result.user_id,
        tenantId: result.tenant_id,
        fullName: result.full_name,
        email: result.email,
        token: result.token,
      });
      navigate(result.role === "admin" ? "/admin" : "/doctor", { replace: true });
    } catch (err) {
      setError(err.message || "Sign up failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page auth-page">
      <PublicNav />
      <section className="auth-shell">
      <Card title="Sign Up" className="auth-card">
        <img className="login-logo" src={brandAssets.logo} alt="Medical Record Summarization logo" />
        <p>Create a demo workspace account. Role access is controlled by account permissions.</p>
        <label className="field"><span>Full name *</span><input required value={form.full_name} onChange={(event) => update("full_name", event.target.value)} placeholder="Nguyen Van A" /></label>
        <label className="field"><span>Email *</span><input required type="email" value={form.email} onChange={(event) => update("email", event.target.value)} placeholder="doctor@example.org" /></label>
        {form.email && !emailValid && <p className="error-text">Use a valid email address.</p>}
        <div className="password-header">
          <span>Password *</span>
          <Button variant="secondary" icon={Sparkles} onClick={autoGeneratePassword}>Auto Generate</Button>
        </div>
        <label className="field"><input required type="password" value={form.password} onChange={(event) => update("password", event.target.value)} placeholder="At least 10 chars, A-z, number, symbol" /></label>
        <PasswordMeter strength={strength} checks={checks} />
        <label className="field"><span>Confirm password *</span><input required type="password" value={form.confirm_password} onChange={(event) => update("confirm_password", event.target.value)} /></label>
        {form.confirm_password && !passwordsMatch && <p className="error-text">Passwords do not match.</p>}
        <label className="field">
          <span>Demo role</span>
          <select value={form.role} onChange={(event) => update("role", event.target.value)}>
            <option value="doctor">Doctor</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <p className="muted">In production, role assignment should be controlled by an administrator or identity provider.</p>
        {error && <p className="warning-line">{error}</p>}
        <div className="public-actions">
          <Button icon={UserPlus} disabled={loading || !canSubmit} onClick={submit}>{loading ? "Creating..." : "Create Account"}</Button>
          <Link to="/login"><Button variant="secondary" icon={KeyRound}>Sign In</Button></Link>
        </div>
      </Card>
      <aside className="auth-visual" style={{ "--thumbnail-image": `url(${brandAssets.images[0]})` }}>
        <div>
          <span><ShieldCheck aria-hidden="true" size={16} /> Secure demo access</span>
          <strong>Start with governed review paths</strong>
          <p>Accounts route users into doctor or admin workspaces while keeping clinical summaries auditable.</p>
        </div>
      </aside>
      </section>
    </main>
  );
}

function PasswordMeter({ strength, checks }) {
  return (
    <div className="password-meter">
      <div className="password-meter-bar"><span className={strength.className} style={{ width: `${(strength.score / 5) * 100}%` }} /></div>
      <strong className={`meter-label ${strength.className}`}>Password strength: {strength.label}</strong>
      <div className="password-checks">
        {checks.map((item) => <span key={item.key} className={item.passed ? "passed" : ""}>{item.passed ? "Pass" : "Todo"}: {item.label}</span>)}
      </div>
    </div>
  );
}

