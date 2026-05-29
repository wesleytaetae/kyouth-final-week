import { FormEvent, useEffect, useState } from "react";

type Item = {
  id: number;
  name: string;
  created_at: string;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function loadItems() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${apiBaseUrl}/api/items`);
      if (!response.ok) {
        throw new Error("Failed to load items");
      }

      const data = (await response.json()) as Item[];
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadItems();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${apiBaseUrl}/api/items`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: name.trim() }),
      });

      if (!response.ok) {
        throw new Error("Failed to create item");
      }

      const createdItem = (await response.json()) as Item;
      setItems((current) => [createdItem, ...current]);
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="card">
        <p className="eyebrow">FastAPI + React + SQLite</p>
        <h1>Simple starter app</h1>
        <p className="lede">
          Add a few records to SQLite through FastAPI and render them in React.
        </p>

        <form className="item-form" onSubmit={handleSubmit}>
          <input
            aria-label="Item name"
            className="text-input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Enter an item name"
          />
          <button className="submit-button" disabled={submitting}>
            {submitting ? "Saving..." : "Add item"}
          </button>
        </form>

        {error ? <p className="error-message">{error}</p> : null}

        <div className="list-block">
          <div className="list-header">
            <h2>Items</h2>
            <button className="ghost-button" onClick={loadItems} type="button">
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="state-message">Loading items...</p>
          ) : items.length === 0 ? (
            <p className="state-message">No items yet. Add one above.</p>
          ) : (
            <ul className="item-list">
              {items.map((item) => (
                <li key={item.id} className="item-row">
                  <span>{item.name}</span>
                  <time>{new Date(item.created_at).toLocaleString()}</time>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

