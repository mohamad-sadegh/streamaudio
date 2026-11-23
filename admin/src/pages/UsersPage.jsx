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
        setError("تغییری نیست");
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
    if (!confirm("این کاربر مدیر برای همیشه حذف شود؟")) return;
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
        <h1>کاربران</h1>
        <p className="muted">
          حساب‌های ورود به پنل با نقش مدیر. ناشران اعتبارنامه دستگاه هستند و جداگانه
          مدیریت می‌شوند.
        </p>

        <form className="create-form users-form" onSubmit={createUser}>
          <input
            placeholder="نام کاربری"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="off"
          />
          <input
            type="password"
            placeholder="رمز عبور (حداقل ۸ کاراکتر)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          <button type="submit" disabled={busy}>
            ایجاد کاربر
          </button>
        </form>

        {error ? <p className="error">{error}</p> : null}

        <div className="table">
          {users.length === 0 ? (
            <p className="muted">هنوز کاربری نیست.</p>
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
                      placeholder="رمز جدید (اختیاری)"
                      value={editPassword}
                      onChange={(e) => setEditPassword(e.target.value)}
                      minLength={8}
                      autoComplete="new-password"
                    />
                    <div className="row-actions">
                      <button type="submit" disabled={busy}>
                        ذخیره
                      </button>
                      <button type="button" className="ghost" onClick={cancelEdit}>
                        انصراف
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="row-main">
                      <div className="row-title">
                        <strong>{u.username}</strong>
                        <span className="tag">{u.role === "admin" ? "مدیر" : u.role}</span>
                        {u.id === user?.id ? (
                          <span className="tag">شما</span>
                        ) : null}
                      </div>
                      <p className="muted small">
                        ایجاد شده{" "}
                        {u.createdAt
                          ? new Date(u.createdAt).toLocaleString("fa-IR")
                          : "—"}
                      </p>
                    </div>
                    <div className="row-actions">
                      <button type="button" className="ghost" onClick={() => startEdit(u)}>
                        ویرایش
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => remove(u.id)}
                        disabled={u.id === user?.id}
                      >
                        حذف
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
