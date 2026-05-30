import { FormEvent, useState } from "react";

type Mode = "buyer" | "seller";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const starterPrompts: Record<Mode, string[]> = {
  buyer: [
    "Any good options for a smart tv?",
    "What is the highest rated product available? Give me only 1 answer.",
    "Are there any good deals for USB-C cables now?",
  ],
  seller: [
    "How should I price my iPhone 15 USB cable?",
    "What is the single most expensive item on sale in the market now?",
    "How should I price a smart watch competitively?",
  ],
};

function createAssistantReply(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

export default function App() {
  const [mode, setMode] = useState<Mode>("buyer");
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: JSON.stringify(
        {
          status: "ready",
          instructions:
            "Pick buyer or seller mode, ask a question, and the raw API JSON will appear here.",
        },
        null,
        2,
      ),
    },
  ]);

  async function sendPrompt(message: string) {
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };

    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${apiBaseUrl}/api/${mode}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: trimmed }),
      });

      const data = response.ok
        ? await response.json()
        : {
            status: response.status,
            error: "Request failed",
            details: await response.text(),
          };

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: createAssistantReply(data),
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: JSON.stringify(
            {
              error: message,
            },
            null,
            2,
          ),
        },
      ]);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await sendPrompt(draft);
  }

  return (
    <main className="page-shell">
      <section className="chat-card">
        <div className="hero-block">
          <p className="eyebrow">Amazon Deal Assistant</p>
          <h1>Chat with the buyer and seller endpoints</h1>
          <p className="lede">
            The frontend now talks to the new FastAPI assistant routes and prints
            the raw JSON response so product rendering can be handled later.
          </p>
        </div>

        <div className="mode-bar" role="tablist" aria-label="Assistant mode">
          <button
            className={`mode-pill ${mode === "buyer" ? "active" : ""}`}
            onClick={() => setMode("buyer")}
            type="button"
          >
            Buyer mode
          </button>
          <button
            className={`mode-pill ${mode === "seller" ? "active" : ""}`}
            onClick={() => setMode("seller")}
            type="button"
          >
            Seller mode
          </button>
        </div>

        <div className="prompt-strip">
          {starterPrompts[mode].map((prompt) => (
            <button
              key={prompt}
              className="prompt-chip"
              onClick={() => void sendPrompt(prompt)}
              type="button"
              disabled={submitting}
            >
              {prompt}
            </button>
          ))}
        </div>

        {error ? <p className="error-message">{error}</p> : null}

        <div className="chat-log" aria-live="polite">
          {messages.map((message) => (
            <article
              key={message.id}
              className={`message-bubble ${message.role === "user" ? "user" : "assistant"}`}
            >
              <div className="message-label">
                {message.role === "user" ? `${mode} prompt` : "assistant json"}
              </div>
              {message.role === "assistant" ? (
                <pre className="json-block">{message.content}</pre>
              ) : (
                <p className="user-text">{message.content}</p>
              )}
            </article>
          ))}

          {submitting ? (
            <article className="message-bubble assistant pending">
              <div className="message-label">assistant json</div>
              <p className="pending-text">Waiting for backend response...</p>
            </article>
          ) : null}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <label className="composer-label" htmlFor="message">
            Ask the {mode} endpoint
          </label>
          <textarea
            id="message"
            className="composer-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              mode === "buyer"
                ? "Ask for a deal, cheapest item, highest rated product, or category suggestion..."
                : "Ask for pricing guidance, positioning, or comparable products..."
            }
            rows={4}
          />
          <div className="composer-footer">
            <p className="composer-hint">
              Request target: <code>/api/{mode}/query</code>
            </p>
            <button className="submit-button" disabled={submitting} type="submit">
              {submitting ? "Sending..." : "Send"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
