Chapter 7Chatbot builder


> Create a retrieval-grounded chatbot from your own knowledge base, test it in the browser, and — on a paid plan — publish it as an embeddable widget for any site.

## At a glance

| | |
|---|---|
| **Who it's for** | any signed-in user — no code required |
| **How it answers** | retrieval over your uploaded documents, grounded and cited |
| **Find it at** | profile menu → **Chatbots** (`/app/chatbots`) |
| **Free plan** | build & test, up to 2 bots |
| **Pro plan** | publish & embed, up to 10 bots |
| **Billing** | profile menu → **Billing** (`/app/billing`) |

## Building a bot

From **Chatbots**, create a bot and give it a knowledge base — upload the documents it should answer from. Set its **persona** (the system prompt that fixes its voice and scope), then open the **Test** tab and talk to it in the browser. The test chat is grounded in exactly what you uploaded: if the answer is not in your documents, the bot says so rather than inventing one. The test conversation persists while you switch tabs, and a **Clear chat** button resets it.

## Plans

Building and testing are free. **Publishing** — making a bot reachable from outside the builder — requires the **Pro** plan, which is the cost guard: a free account can design and try a bot end to end, but cannot put it live.

| | Free | Pro |
|---|---|---|
| Build & test | ✓ | ✓ |
| Bots | up to 2 | up to 10 |
| Publish & embed | — | ✓ |

Upgrade from the **Billing** page, which uses Stripe's hosted checkout and billing portal — no card details ever touch this site.

## Publishing & embedding

On a Pro plan, the bot's **Embed** tab publishes it and gives you a one-line snippet to drop into any page:

```html
<script src="https://ml-portfolio-rho.vercel.app/embed/v1.js"
        data-bot="pk_live_…" async></script>
```

The script adds a floating chat bubble that opens the bot in a sandboxed iframe. The `pk_live_…` key is **public** — it only starts a chat — and regenerating it invalidates the old one.

## How an embedded bot is kept safe

A public key on a public page could be copied, so the widget does not rely on it being secret. Several controls bound what it can do:

- **Origin allowlist** — a chat only starts from the sites you list.
- **Short-lived session token** — the page mints a token bound to your bot and the calling site; it expires in minutes.
- **Rate limit** — per-visitor message throttling.
- **Daily message cap** — a hard ceiling on messages per day, so a runaway or abusive page cannot run up unbounded cost.
- **Kill switch** — unpublish the bot and every embed stops at once.

The origin check steers ordinary use to the right sites; the rate limit, daily cap, and kill switch are the hard backstops.
