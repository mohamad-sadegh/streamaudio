import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Roles } from "../api.js";

const FALLBACK = [
  {
    id: "admin",
    name: "مدیر",
    description:
      "حساب ورود به پنل. می‌تواند ناشران و کاربران را مدیریت کند و به استریم‌ها گوش دهد.",
  },
  {
    id: "publisher",
    name: "ناشر",
    description:
      "اعتبارنامه دستگاه برای انتشار WHIP. ورود به پنل نیست — از بخش ناشران بسازید.",
  },
];

export default function RolesPage() {
  const [roles, setRoles] = useState(FALLBACK);
  const [error, setError] = useState("");

  useEffect(() => {
    Roles.list()
      .then((data) => {
        if (data.roles?.length) setRoles(data.roles);
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main className="page">
      <section className="panel">
        <h1>نقش‌ها</h1>
        <p className="muted">نقش‌های ثابت سیستم. نقش سفارشی پشتیبانی نمی‌شود.</p>

        {error ? <p className="error">{error}</p> : null}

        <div className="role-grid">
          {roles.map((role) => (
            <article key={role.id} className="role-card">
              <div className="row-title">
                <strong>{role.name}</strong>
                <span className="tag">{role.id}</span>
              </div>
              <p className="muted">{role.description}</p>
              {role.id === "admin" ? (
                <Link className="btn-link" to="/users">
                  مدیریت کاربران
                </Link>
              ) : null}
              {role.id === "publisher" ? (
                <Link className="btn-link" to="/publishers">
                  ایجاد ناشر
                </Link>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
