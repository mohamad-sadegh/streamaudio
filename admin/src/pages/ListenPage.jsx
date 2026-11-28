import { useEffect } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";

/** Legacy listen route — redirect into the publisher management page. */
export default function ListenPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const slot = params.get("slot");

  useEffect(() => {
    // no-op; redirect below
  }, []);

  if (!id) {
    return (
      <main className="page">
        <p className="error">ناشر پیدا نشد</p>
        <Link to="/publishers">بازگشت</Link>
      </main>
    );
  }

  const target = slot != null ? `/publishers/${id}?slot=${slot}` : `/publishers/${id}`;
  return <Navigate to={target} replace />;
}
