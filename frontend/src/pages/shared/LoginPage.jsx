import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, KeyRound, ShieldCheck, UserPlus } from "lucide-react";
import Card from "../../components/common/Card.jsx";
import Button from "../../components/common/Button.jsx";
import PublicNav from "../../components/navigation/PublicNav.jsx";
import { useRole } from "../../hooks/useRole.js";
import { authApi } from "../../services/authApi.js";
import { brandAssets } from "../../assets/branding.js";
import { useEffect, useRef, useState } from "react";
import { validateEmail } from "../../utils/authValidation.js";

export default function LoginPage() {
  const navigate = useNavigate();
  const { session, updateSession, login } = useRole();
  const googleButtonRef = useRef(null);
  const [role, setRole] = useState("doctor");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [authConfig, setAuthConfig] = useState(null);

  useEffect(() => {
    authApi.config().then(setAuthConfig).catch(() => setAuthConfig({ google_client_id_configured: false }));
  }, []);

  useEffect(() => {
    if (!authConfig?.google_client_id_configured || !authConfig?.google_client_id) {
      return;
    }

    const scriptId = "google-identity-services";
    const renderButton = () => {
      if (!window.google?.accounts?.id || !googleButtonRef.current) {
        return;
      }
      googleButtonRef.current.innerHTML = "";
      window.google.accounts.id.initialize({
        client_id: authConfig.google_client_id,
        callback: handleGoogleCredential,
      });
      window.google.accounts.id.renderButton(googleButtonRef.current, {
        theme: "filled_blue",
        size: "large",
        type: "standard",
        shape: "pill",
        text: "continue_with",
        logo_alignment: "left",
        width: googleButtonRef.current.clientWidth || 360,
      });
    };

    const existingScript = document.getElementById(scriptId);
    if (existingScript) {
      renderButton();
      return;
    }

    const script = document.createElement("script");
    script.id = scriptId;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = renderButton;
    script.onerror = () => setError("Could not load Google Identity Services. Check network access and Google OAuth configuration.");
    document.head.appendChild(script);
  }, [authConfig, role, session.tenantId]);

  const applySession = (result, message = "Signed in successfully.") => {
    login({
      role: result.role,
      userId: result.user_id,
      tenantId: result.tenant_id,
      fullName: result.full_name,
      email: result.email,
      token: result.token,
    });
    setSuccess(message);
    navigate(result.role === "admin" ? "/admin" : "/doctor", { replace: true });
  };

  const handleGoogleCredential = async (response) => {
    if (!response?.credential) {
      setError("Google sign-in did not return a credential.");
      return;
    }
    setGoogleLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await authApi.googleLogin({
        credential: response.credential,
        role,
        tenant_id: session.tenantId,
      });
      applySession(result, "Signed in with Google successfully.");
    } catch (err) {
      setError(googleSignInErrorMessage(err));
    } finally {
      setGoogleLoading(false);
    }
  };

  const enter = async () => {
    const identifier = session.email || session.userId;
    if (!identifier || identifier.trim().length < 2) {
      setError("Email or username is required.");
      return;
    }
    if (identifier.includes("@") && !validateEmail(identifier)) {
      setError("Use a valid email address.");
      return;
    }
    if (!password) {
      setError("Password is required.");
      return;
    }
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await authApi.login({
        role,
        email: session.email || session.userId,
        password,
        tenant_id: session.tenantId,
      });
      applySession(result);
    } catch (err) {
      setError(err.message || "Sign in failed.");
    } finally {
      setLoading(false);
    }
  };
  return (
    <main className="login-page auth-page">
      <PublicNav />
      <section className="auth-shell">
        <Card title="Sign In" className="auth-card">
          <img className="login-logo" src={brandAssets.logo} alt="Medical Record Summarization logo" />
          <p>Access the Medical Record Summarization workspace with your account role.</p>
          <label className="field">
            <span>Email or username</span>
            <input required value={session.email || session.userId} onChange={(event) => updateSession({ userId: event.target.value, email: event.target.value })} placeholder="doctor@example.org" />
          </label>
          <label className="field">
            <span>Password</span>
            <input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <label className="field">
            <span>Account role</span>
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="doctor">Doctor</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <p className="muted">Role access is controlled by account permissions. Role selection is available here for demo mode.</p>
          {authConfig?.google_client_id_configured ? (
            <div className="google-signin-wrap polished-google">
              <span className="google-helper">Continue with your configured Google workspace account</span>
              <div ref={googleButtonRef} className={googleLoading ? "google-button-loading" : ""} />
              {googleLoading && <p className="muted">Signing in with Google...</p>}
            </div>
          ) : (
            <button className="google-button" type="button" onClick={() => setError("GOOGLE_CLIENT_ID is not configured.")}>
              Continue with Google (not configured)
            </button>
          )}
          <Link className="inline-link" to="/forgot-password">Forget Password?</Link>
          {success && <p className="review-result"><strong>{success}</strong></p>}
          {error && <p className="warning-line">{error}</p>}
          <div className="public-actions">
            <Button icon={KeyRound} onClick={enter} disabled={loading || !password}>{loading ? "Signing in..." : "Sign In"}</Button>
            <Link to="/signup"><Button variant="secondary" icon={UserPlus}>Create Account</Button></Link>
          </div>
        </Card>
        <AuthVisual title="Evidence stays visible" image={brandAssets.images[3]} />
      </section>
    </main>
  );
}

function AuthVisual({ title, image }) {
  return (
    <aside className="auth-visual" style={{ "--thumbnail-image": `url(${image})` }}>
      <div>
        <span><ShieldCheck aria-hidden="true" size={16} /> Clinical review required</span>
        <strong>{title}</strong>
        <p>Generated summaries remain drafts until an authorized reviewer approves the final version.</p>
        <Link to="/about"><Button variant="secondary" className="learn-more-button" icon={ArrowRight} iconPosition="right">Learn More</Button></Link>
      </div>
    </aside>
  );
}

function googleSignInErrorMessage(error) {
  const message = error?.message || "Google sign-in failed.";
  if (message.includes("404")) {
    return "Google sign-in endpoint is not available on the running backend. Restart the backend so /api/v1/auth/google is registered.";
  }
  if (message.includes("GOOGLE_CLIENT_ID")) {
    return "GOOGLE_CLIENT_ID is not configured on the backend.";
  }
  if (message.includes("Invalid Google OAuth credential")) {
    return "Google returned an invalid credential for this app origin. Check the OAuth client ID and Authorized JavaScript origins.";
  }
  return message;
}
