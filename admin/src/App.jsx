import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Auth } from "./api.js";
import AdminLayout from "./components/AdminLayout.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import PublishersPage from "./pages/PublishersPage.jsx";
import PublisherManagePage from "./pages/PublisherManagePage.jsx";
import UsersPage from "./pages/UsersPage.jsx";
import RolesPage from "./pages/RolesPage.jsx";
import ListenPage from "./pages/ListenPage.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Auth.me()
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="boot">
        <div className="boot-pulse" />
        <p>در حال بارگذاری…</p>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          user ? (
            <Navigate to="/publishers" replace />
          ) : (
            <LoginPage onLogin={setUser} />
          )
        }
      />
      <Route
        element={
          user ? (
            <AdminLayout user={user} onLogout={() => setUser(null)} />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      >
        <Route path="/" element={<Navigate to="/publishers" replace />} />
        <Route path="/publishers" element={<PublishersPage />} />
        <Route path="/publishers/:id" element={<PublisherManagePage />} />
        <Route path="/users" element={<UsersPage user={user} />} />
        <Route path="/roles" element={<RolesPage />} />
        <Route path="/listen/:id" element={<ListenPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/publishers" replace />} />
    </Routes>
  );
}
