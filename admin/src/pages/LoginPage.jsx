import { useState } from "react";
import { Auth } from "../api.js";

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await Auth.login(username, password);
      onLogin({ username: data.username, id: data.id });
    } catch (err) {
      setError(err.message || "ورود ناموفق بود");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-atmosphere" aria-hidden />
      <form className="login-panel" onSubmit={submit}>
        <p className="brand">پژواک</p>
        <h1>ورود مدیر</h1>
        <p className="muted">دسترسی فقط با دعوت است. ثبت‌نام عمومی وجود ندارد.</p>

        <label>
          نام کاربری
          <input
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>

        <label>
          رمز عبور
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error ? <p className="error">{error}</p> : null}

        <button type="submit" disabled={busy}>
          {busy ? "در حال ورود…" : "ورود"}
        </button>
      </form>
    </div>
  );
}
