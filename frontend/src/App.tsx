import { FormEvent, useState } from "react";

type Mode = "buyer" | "seller";

type Product = {
  id?: string;
  product_name?: string;
  discounted_price_myr?: number | string;
  actual_price_myr?: number | string;
  discount_percentage?: number | string;
  rating?: number | string;
  img_link?: string;
  product_link?: string;
};

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

function ProductCard({ product }: { product: Product }) {
  const title = product.product_name ?? "Unknown Product";
  const imgSrc = product.img_link ?? "https://placehold.co/150x150?text=No+Image";
  const rating = product.rating ?? "N/A";
  const discount = product.discount_percentage;
  
  const currentPrice = typeof product.discounted_price_myr === "number"
    ? `RM ${product.discounted_price_myr.toFixed(2)}`
    : (product.discounted_price_myr ? `RM ${product.discounted_price_myr}` : "N/A");

  const originalPrice = typeof product.actual_price_myr === "number"
    ? `RM ${product.actual_price_myr.toFixed(2)}`
    : (product.actual_price_myr ? `RM ${product.actual_price_myr}` : null);

  let discountText = null;
  if (discount !== undefined && discount !== null) {
    const numericDiscount = Number(discount);
    if (!isNaN(numericDiscount)) {
      discountText = numericDiscount > 0 && numericDiscount < 1 
        ? `${Math.round(numericDiscount * 100)}% OFF` 
        : `${Math.round(numericDiscount)}% OFF`;
    } else if (String(discount).trim().length > 0) {
      discountText = String(discount).includes("%") ? String(discount) : `${discount}% OFF`;
    }
  }

  return (
    <div className="product-card">
      <div className="product-image-wrapper">
        {discountText && <span className="discount-badge">{discountText}</span>}
        <img 
          src={imgSrc} 
          alt={title} 
          className="product-image" 
          onError={(e) => { e.currentTarget.src = "https://placehold.co/150x150?text=No+Image+Available"; }}
        />
      </div>
      <div className="product-details">
        <div className="product-rating-row">⭐ {rating}</div>
        <h3 className="product-title" title={title}>{title}</h3>
        <div className="product-price-container">
          <span className="price-current">{currentPrice}</span>
          {originalPrice && <span className="price-original">List: {originalPrice}</span>}
        </div>
        {product.product_link && (
          <a href={product.product_link} target="_blank" rel="noopener noreferrer" className="view-deal-btn">
            View Deal ↗
          </a>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState<Mode>("buyer");
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [isPromptsExpanded, setIsPromptsExpanded] = useState(true);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Welcome! Pick buyer or seller mode, ask a question, and data profiles will appear here.",
    },
  ]);
  
  // Track active visual products to render in the right panel canvas
  const [activeProducts, setActiveProducts] = useState<Product[]>([]);

  async function sendPrompt(message: string) {
    const trimmed = message.trim();
    if (!trimmed) return;

    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: trimmed };

    // Clear active cards immediately upon sending a new query as requested
    setActiveProducts([]);
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${apiBaseUrl}/api/${mode}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      const data = await response.json();

      if (response.ok) {
        // Parse array structures to look for list cards
        let productsFound: Product[] = [];
        if (Array.isArray(data)) {
          productsFound = data;
        } else if (data && Array.isArray(data.products)) {
          productsFound = data.products;
        } else if (data && Array.isArray(data.items)) {
          productsFound = data.items;
        } else if (data && (data.product_name || data.title)) {
          productsFound = [data]; // Single item wrapping fallback
        }

        setActiveProducts(productsFound);
        
        // Push a conversational confirmation text line to the Chat log
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: productsFound.length > 0 
              ? `I found ${productsFound.length} items matching your request. Check the right panel details!`
              : JSON.stringify(data, null, 2)
          },
        ]);
      } else {
        setError("Failed to fetch response payload.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error occurred.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page-shell">
      {/* Dynamic App Header */}
      <header className="app-header">
        <span className="header-logo">🤖 LLM Deal Assistant</span>
        <div className="mode-bar" style={{ margin: 0 }} role="tablist">
          <button className={`mode-pill ${mode === "buyer" ? "active" : ""}`} onClick={() => setMode("buyer")}>
            Buyer Mode
          </button>
          <button className={`mode-pill ${mode === "seller" ? "active" : ""}`} onClick={() => setMode("seller")}>
            Seller Mode
          </button>
        </div>
      </header>

      {/* Reworked 40/60 Workspace Split View */}
      <div className="workspace-container">
        
        {/* LEFT PANEL: Chat Context Logging */}
        <section className="chat-panel">
          <div className="chat-log-scrollable">
            {messages.map((msg) => (
              <article key={msg.id} className={`message-bubble ${msg.role}`}>
                <strong>{msg.role === "user" ? "You" : "AI Assistant"}:</strong>
                <p style={{ margin: "4px 0 0 0" }}>{msg.content}</p>
              </article>
            ))}
            {submitting && (
              <p style={{ fontStyle: "italic", color: "#64748b" }}>Searching market databases...</p>
            )}
            {error && <p className="error-message">{error}</p>}
          </div>

          {/* Composer Input Area & Starter Prompt Tucking Container */}
          <div className="composer-fixed-bottom">
  
  {/* Header Row for the prompts drawer */}
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#355070", uppercase: "true" }}>
      Starter Prompts
    </span>
    <button
      type="button"
      onClick={() => setIsPromptsExpanded(!isPromptsExpanded)}
      style={{
        background: "none",
        border: "none",
        color: "#355070",
        cursor: "pointer",
        fontSize: "0.8rem",
        padding: "4px 8px"
      }}
    >
      {isPromptsExpanded ? "Hide ▲" : "Show ▼"}
    </button>
  </div>

  {/* Dynamic Conditional Render based on state */}
  {isPromptsExpanded && (
    <div className="prompt-strip-left">
      {starterPrompts[mode].map((prompt) => (
        <button 
          key={prompt} 
          className="prompt-chip-small" 
          onClick={() => void sendPrompt(prompt)}
          disabled={submitting}
        >
          {prompt}
        </button>
      ))}
    </div>
  )}

  <form onSubmit={(e) => { e.preventDefault(); sendPrompt(draft); }} style={{ display: "flex", gap: "8px" }}>
    <input
      className="composer-input"
      style={{ padding: "10px", borderRadius: "8px", border: "1px solid #cbd5e1", flex: 1 }}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      placeholder={`Ask the ${mode} engine...`}
    />
    <button className="submit-button" type="submit" disabled={submitting} style={{ height: "auto" }}>
      Send
    </button>
  </form>
</div>
        </section>

        {/* RIGHT PANEL: Visual Cards & Search Evidence Canvas */}
        <section className="results-panel">
          <div className="results-canvas-scrollable">
            <h2 className="panel-title">Results Panel (Evidence & Product Cards)</h2>
            
            {activeProducts.length > 0 ? (
              <div className="products-grid">
                {activeProducts.map((product, idx) => (
                  <ProductCard key={product.id ?? idx} product={product} />
                ))}
              </div>
            ) : (
              <div style={{ color: "#64748b", textAlign: "center", marginTop: "40px" }}>
                {submitting ? "Gathering live inventory data profiles..." : "No active data requested yet. Pick a prompt to view data matching records."}
              </div>
            )}
          </div>
        </section>

      </div>
    </main>
  );
}