import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Roles } from "../api.js";

const FALLBACK = [
  {
    id: "admin",
    name: "Admin",
    description:
      "Panel login account. Can manage publishers, users, and listen to streams.",
  },
  {
    id: "publisher",
    name: "Publisher",
    description:
      "Device credential for WHIP publish. Not a panel login — create via Publishers.",
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
        <h1>Roles</h1>
        <p className="muted">
          Fixed system roles. Custom roles are not supported.
        </p>

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
                  Manage users
                </Link>
              ) : null}
              {role.id === "publisher" ? (
                <Link className="btn-link" to="/publishers">
                  Create publisher
                </Link>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
