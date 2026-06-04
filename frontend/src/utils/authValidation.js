export function validateEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value || "");
}

export function passwordChecks(password) {
  return [
    { key: "length", label: "At least 10 characters", passed: password.length >= 10 },
    { key: "lower", label: "Lowercase letter", passed: /[a-z]/.test(password) },
    { key: "upper", label: "Uppercase letter", passed: /[A-Z]/.test(password) },
    { key: "number", label: "Number", passed: /\d/.test(password) },
    { key: "symbol", label: "Symbol", passed: /[^A-Za-z0-9]/.test(password) },
  ];
}

export function passwordScore(password) {
  return passwordChecks(password).filter((item) => item.passed).length;
}

export function passwordStrength(password) {
  const score = passwordScore(password);
  if (score <= 2) return { score, label: "Weak", className: "danger" };
  if (score <= 4) return { score, label: "Medium", className: "warning" };
  return { score, label: "Strong", className: "success" };
}

export function generatePassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*?";
  const required = ["A", "m", "7", "!"];
  const randomValues = crypto.getRandomValues(new Uint32Array(12));
  const rest = Array.from(randomValues, (value) => alphabet[value % alphabet.length]);
  return [...required, ...rest].sort(() => Math.random() - 0.5).join("");
}
