import { useCallback, useEffect, useState } from "react";
import { Users } from "../api.js";

export default function UsersPage({ user }) {
  const [users, setUsers] = useState([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [editId, setEditId] = useState(null);
  const [editUsername, setEditUsername] = useState("");
  const [editPassword, setEditPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const data = await Users.list();
    setUsers(data.users || []);
  }, []);

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [refresh]);

  async function createUser(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await Users.create(username, password);
      setUsername("");
      setPassword("");
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function startEdit(u) {
    setEditId(u.id);
    setEditUsername(u.username);
    setEditPassword("");
    setError("");
  }

  function cancelEdit() {
    setEditId(null);
    setEditUsername("");
    setEditPassword("");
  }

  async function saveEdit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const patch = {};
      const current = users.find((u) => u.id === editId);
      if (editUsername && editUsername !== current?.username) {
        patch.username = editUsername;
      }
      if (editPassword) {
        patch.password = editPassword;
      }
      if (Object.keys(patch).length === 0) {
        setError("No changes");
        return;
      }
      await Users.update(editId, patch);
      cancelEdit();
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!confirm("Delete this admin user permanently?")) return;
    setError("");
    try {
      await Users.remove(id);
      if (editId === id) cancelEdit();
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="page">
      <section className="panel">
        <h1>Users</h1>
        <p className="muted">
          Panel login accounts with the admin role. Publishers are device
          credentials managed separately.
        </p>

        <form className="create-form users-form" onSubmit={createUser}>
          <input
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="off"
          />
          <input
            type="password"
            placeholder="password (min 8)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          <button type="submit" disabled={busy}>
            Create user
          </button>
        </form>

        {error ? <p className="error">{error}</p> : null}

        <div className="table">
          {users.length === 0 ? (
            <p className="muted">No users yet.</p>
          ) : (
            users.map((u) => (
              <article key={u.id} className="row">
                {editId === u.id ? (
                  <form className="edit-form" onSubmit={saveEdit}>
                    <input
                      value={editUsername}
                      onChange={(e) => setEditUsername(e.target.value)}
                      required
                      autoComplete="off"
                    />
                    <input
                      type="password"
                      placeholder="new password (optional)"
                      value={editPassword}
                      onChange={(e) => setEditPassword(e.target.value)}
                      minLength={8}
                      autoComplete="new-password"
                    />
                    <div className="row-actions">
                      <button type="submit" disabled={busy}>
                        Save
                      </button>
                      <button type="button" className="ghost" onClick={cancelEdit}>
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="row-main">
                      <div className="row-title">
                        <strong>{u.username}</strong>
                        <span className="tag">{u.role}</span>
                        {u.id === user?.id ? (
                          <span className="tag">you</span>
                        ) : null}
                      </div>
                      <p className="muted small">
                        Created{" "}
                        {u.createdAt
                          ? new Date(u.createdAt).toLocaleString()
                          : "—"}
                      </p>
                    </div>
                    <div className="row-actions">
                      <button type="button" className="ghost" onClick={() => startEdit(u)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => remove(u.id)}
                        disabled={u.id === user?.id}
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
